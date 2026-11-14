"""Server-owned workflow templates over the typed registry and approval engine."""

import hashlib
from pathlib import Path

from filelock import FileLock, Timeout
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import ValidationError

from bizmate.agents.graph import build_graph
from bizmate.agents.languages import detect_language, say
from bizmate.agents.planner import GoalExtraction
from bizmate.agents.recovery import Recovery, RecoveryExhausted
from bizmate.domain.context import require_context
from bizmate.domain.errors import AccessDenied
from bizmate.domain.lifecycle import transition_task
from bizmate.domain.models import (
    Intent,
    PlanStep,
    Scope,
    Task,
    TaskEvent,
    TaskStatus,
    Verification,
    VerificationResult,
    new_id,
)
from bizmate.services.mock_models import SettlementReport
from bizmate.tools.policy import ActionConflict, ApprovalEngine
from bizmate.tools.registry import PreconditionFailed
from bizmate.workflows.handoff import CapabilityUnavailable, prepare_handoff
from bizmate.workflows.investigation import (
    InvestigationRequest,
    InvestigationState,
    SettlementInvestigation,
)
from bizmate.workflows.review import CampaignEdit
from bizmate.workflows.settlement import SettlementProof, reconcile_settlement


def rupees(paise: int) -> str:
    whole, fraction = divmod(abs(paise), 100)
    return f"{'-' if paise < 0 else ''}{whole}.{fraction:02d}"


TERMINAL = {TaskStatus.COMPLETED, TaskStatus.ESCALATED, TaskStatus.FAILED}


class Orchestrator:
    def __init__(self, repo, registry, services, planner, checkpoint_file: Path):
        self.repo, self.registry, self.services, self.planner = repo, registry, services, planner
        self.checkpoint_file = checkpoint_file
        self.recovery = Recovery(repo, registry, services)
        self.engine = ApprovalEngine(repo, registry)

    def start(
        self,
        context,
        message,
        conversation_id=None,
        preferred_language=None,
        task_id=None,
        extraction: GoalExtraction | None = None,
    ):
        require_context(context)
        context.require(Scope.TASKS_READ, Scope.TASKS_WRITE)
        task_id = task_id or new_id()
        existing = self.repo.get_task(context, task_id)
        if existing:
            if existing.original_request != message or existing.conversation_id != conversation_id:
                raise ActionConflict("Task request key was used with different content")
            return self.run(context, task_id)
        language = detect_language(message) or preferred_language or context.preferred_language
        task = Task(
            task_id=task_id,
            merchant_id=context.merchant_id,
            goal=message.strip()[:180],
            original_request=message,
            conversation_id=conversation_id,
            next_action=say("running", language),
            events=(TaskEvent(kind="request_received", message=message),),
            workflow_data={
                "engine_version": 1,
                "phase": "plan",
                "planning_request": message,
                "preferred_language": str(preferred_language or context.preferred_language),
                "detected_language": detect_language(message),
                "response_language": str(language),
                # Reuse validated chat intake instead of charging for a second model call.
                **({"intake_extraction": extraction.model_dump(mode="json")} if extraction else {}),
            },
        )
        self.repo.save(context, task)
        return self.run(context, task.task_id)

    def message(self, context, task_id, message, event_id=None):
        # Run and message share the same cross-process lock, including task mutation.
        return self.run(context, task_id, message=message, message_event_id=event_id)

    @staticmethod
    def thread_id(context, task_id):
        return hashlib.sha256(f"{context.merchant_id}:{task_id}".encode()).hexdigest()

    def run(self, context, task_id, message=None, campaign_edit=None, message_event_id=None):
        task = self.recovery.task(context, task_id)
        if task.workflow_data.get("engine_version") != 1:
            raise ActionConflict("This legacy task has no resumable orchestration plan")
        thread = self.thread_id(context, task_id)
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        locks = self.checkpoint_file.parent / ".workflow-locks"
        locks.mkdir(exist_ok=True)
        try:
            with FileLock(str(locks / (thread + ".lock")), timeout=0):
                task = self.recovery.task(context, task_id)
                if message_event_id:
                    previous = next(
                        (e for e in task.events if e.event_id == message_event_id), None
                    )
                    if previous:
                        if previous.kind != "merchant_message" or previous.message != message:
                            raise ActionConflict("Message ID was used with different content")
                        # Replayed chat must never execute an approved action.
                        if task.workflow_data.get("phase") not in {"plan", "prepare"}:
                            return task
                        message = None
                current = task.approvals[task.workflow_data.get("approval_start", 0) :]
                if task.workflow_data["phase"] == "action" and current:
                    approval = current[-1]
                    if approval.decision == "approved":
                        context.require(Scope.TASKS_APPROVE)
                        if approval.approver != context.actor_id:
                            raise AccessDenied("Only the approving actor can resume this action")
                if campaign_edit is not None:
                    task = self._edit_campaign(context, task, campaign_edit)
                if message is not None:
                    language = detect_language(message) or task.workflow_data["response_language"]
                    data = {
                        **task.workflow_data,
                        "detected_language": detect_language(message),
                        "response_language": str(language),
                    }
                    if task.status == TaskStatus.AWAITING_INPUT:
                        data.update(
                            phase="plan",
                            input_pending=False,
                            planning_request=(
                                task.original_request + "\n" + message
                                if task.intent == Intent.WIN_BACK
                                and task.workflow_data.get("extraction", {}).get("offer_message")
                                is None
                                else message
                            ),
                        )
                    task = self.repo.save(
                        context,
                        task.with_updates(
                            workflow_data=data,
                            events=(
                                *task.events,
                                TaskEvent(
                                    event_id=message_event_id or new_id(),
                                    kind="merchant_message",
                                    message=message,
                                ),
                            ),
                        ),
                    )
                if task.status in TERMINAL:
                    return task
                config = {"configurable": {"thread_id": thread}, "recursion_limit": 40}
                with SqliteSaver.from_conn_string(str(self.checkpoint_file)) as saver:
                    graph = build_graph(lambda tid: self._dispatch(context, tid), saver)
                    snapshot = graph.get_state(config)
                    if snapshot.tasks and any(t.interrupts for t in snapshot.tasks):
                        invocation = Command(resume=True)
                    elif snapshot.next:
                        invocation = None  # Resume a process interrupted between nodes.
                    else:
                        invocation = {"task_id": task_id}
                    graph.invoke(invocation, config=config)
                    snapshot = graph.get_state(config)
                    checkpoint_id = snapshot.config["configurable"]["checkpoint_id"]
                    task = self.recovery.task(context, task_id)
                    if task.checkpoint_id != checkpoint_id:
                        task = self.repo.save(
                            context, task.with_updates(checkpoint_id=checkpoint_id)
                        )
                    return task
        except Timeout:
            raise ActionConflict("Task is already running. Reload its saved state") from None

    def _edit_campaign(self, context, task, edit):
        edit = CampaignEdit.model_validate(edit)
        if task.revision != edit.expected_revision:
            raise ActionConflict("Campaign changed. Reload its review before editing")
        if (
            task.intent != Intent.WIN_BACK
            or task.status
            not in {
                TaskStatus.AWAITING_INPUT,
                TaskStatus.AWAITING_APPROVAL,
                TaskStatus.READY,
                TaskStatus.PLANNING,
                TaskStatus.RUNNING,
            }
            or task.receipts
            or task.has_unresolved_execution
        ):
            raise ActionConflict("Only an unexecuted campaign can be edited")
        current = task.approvals[task.workflow_data.get("approval_start", 0) :]
        if current and current[-1].decision != "cancelled":
            approval = current[-1]
            self.engine.decide(
                context, task.task_id, approval.approval_id, "cancel", approval.input_hash
            )
            task = self.recovery.task(context, task.task_id)
        if task.status != TaskStatus.PLANNING:
            task = self._save(context, task, status=TaskStatus.PLANNING, key="campaign_changed")
        data = task.workflow_data
        extraction = {
            **data.get("extraction", {}),
            "offer_message": edit.message,
            "inactivity_days": edit.inactivity_days
            or data.get("extraction", {}).get("inactivity_days", 30),
        }
        language = detect_language(edit.message) or data["response_language"]
        task = self._save(
            context,
            task,
            status=TaskStatus.READY,
            key="campaign_changed",
            workflow_data={
                **data,
                "extraction": extraction,
                "phase": "prepare",
                "input_pending": False,
                "response_language": str(language),
                "read_generation": data.get("read_generation", 0) + 1,
                "approval_start": len(task.approvals),
            },
            plan=(
                PlanStep(
                    task_id=task.task_id,
                    merchant_id=context.merchant_id,
                    step_id="prepare",
                    tool_name="segment_inactive_customers",
                    inputs={"inactivity_days": extraction["inactivity_days"]},
                ),
            ),
            events=(
                *task.events,
                TaskEvent(
                    kind="campaign_review_changed", message=say("campaign_changed", language)
                ),
            ),
        )
        return task

    def _gap(self, context, task_id, capability, reason):
        task = self.recovery.task(context, task_id)
        draft, gap = prepare_handoff(context, task, capability=capability, reason=reason)
        language = task.workflow_data["response_language"]
        gaps = task.capability_gaps if gap in task.capability_gaps else (*task.capability_gaps, gap)
        if task.workflow_data.get("handoff_draft"):
            from bizmate.workflows.review import HandoffDraft

            draft = HandoffDraft.model_validate(task.workflow_data["handoff_draft"])
        task = self._save(
            context,
            task,
            capability_gaps=gaps,
            workflow_data={
                **task.workflow_data,
                "handoff_draft": draft.model_dump(mode="json"),
                "handoff_explanation": say("handoff_limit", language),
            },
            events=(
                *task.events,
                TaskEvent(kind="capability_gap_detected", message=say("handoff_limit", language)),
            ),
        )
        tools = {t.metadata.name for t in self.registry.discover(context, intent=Intent.HANDOFF)}
        if (
            "create_support_ticket" not in tools
            or task.receipts
            or task.has_unresolved_execution
            or task.workflow_data["phase"] in {"verify", "finalize"}
        ):
            self._save(
                context,
                task,
                status=TaskStatus.ESCALATED,
                key="handoff_limit",
                workflow_data={**task.workflow_data, "phase": "review"},
            )
            return "end"
        current = task.approvals[task.workflow_data.get("approval_start", 0) :]
        if current and current[-1].decision != "cancelled":
            if Scope.TASKS_APPROVE not in context.scopes:
                self._save(
                    context,
                    task,
                    status=TaskStatus.ESCALATED,
                    key="handoff_limit",
                    workflow_data={**task.workflow_data, "phase": "review"},
                )
                return "end"
            old = current[-1]
            self.engine.decide(context, task_id, old.approval_id, "cancel", old.input_hash)
            task = self.recovery.task(context, task_id)
        if task.status != TaskStatus.PLANNING:
            task = self._save(context, task, status=TaskStatus.PLANNING, key="handoff_limit")
        self._save(
            context,
            task,
            status=TaskStatus.READY,
            key="handoff_limit",
            intent=Intent.HANDOFF,
            plan=(),
            workflow_data={
                **task.workflow_data,
                "phase": "prepare",
                "approval_start": len(task.approvals),
            },
        )
        return "continue"

    def _save(self, context, task, *, status=None, key=None, **updates):
        if key:
            updates["next_action"] = say(key, task.workflow_data["response_language"])
        task = task.with_updates(**updates)
        if status and task.status != status:
            task = transition_task(task, status, task.next_action)
        return self.repo.save(context, task)

    def _dispatch(self, context, task_id):
        task = self.recovery.task(context, task_id)
        if task.status in TERMINAL:
            return "end"
        phase = task.workflow_data["phase"]
        if phase == "plan" and task.workflow_data.get("input_pending"):
            return "pause"
        try:
            if phase == "plan":
                return self._plan(context, task)
            if phase == "prepare":
                return self._prepare(context, task)
            if phase == "action":
                return self._action(context, task)
            if phase == "verify":
                return self._verify(context, task)
            if phase == "finalize":
                return self._finalize(context, task)
            return "pause"
        except PreconditionFailed as exc:
            task = self.recovery.task(context, task_id)
            if (
                task.intent == Intent.WIN_BACK
                and exc.precondition == "campaign_audience_current"
                and not task.has_unresolved_execution
                and not task.receipts
            ):
                self._edit_campaign(
                    context,
                    task,
                    CampaignEdit(
                        expected_revision=task.revision,
                        message=task.workflow_data["extraction"]["offer_message"],
                    ),
                )
                return "continue"
            raise
        except PermissionError as exc:
            capability = getattr(exc, "capability", "requested_action")
            return self._gap(
                context, task_id, capability, getattr(exc, "reason", "permission_denied")
            )
        except (
            ValueError,
            LookupError,
            TimeoutError,
            ConnectionError,
            RecoveryExhausted,
            ActionConflict,
        ) as exc:
            # Persist a public, localized error. Never place provider/model secrets in events.
            task = self.recovery.task(context, task_id)
            self._save(
                context,
                task,
                status=TaskStatus.ESCALATED,
                key="error",
                workflow_data={
                    **task.workflow_data,
                    "phase": "review",
                    "recovery_error": {"phase": phase, "category": type(exc).__name__},
                },
                events=(
                    *task.events,
                    TaskEvent(
                        kind="recovery_escalated",
                        message=say("error", task.workflow_data["response_language"]),
                    ),
                ),
            )
            return "end"

    def _plan(self, context, task):
        if task.status in {TaskStatus.CREATED, TaskStatus.AWAITING_INPUT}:
            task = self._save(context, task, status=TaskStatus.PLANNING, key="running")
        if task.status != TaskStatus.PLANNING:
            raise ActionConflict("Task must be planning")
        result = task.workflow_data.get("intake_extraction") or self.planner.invoke(
            {
                "request": task.workflow_data["planning_request"],
                "preferred_language": task.workflow_data["response_language"],
            }
        )
        fields = GoalExtraction.model_fields
        try:
            # Adapter extensions cannot inject identity, status, tools or policy.
            goal = GoalExtraction.model_validate({k: result[k] for k in fields if k in result})
        except (KeyError, ValidationError):
            self._save(
                context,
                task,
                status=TaskStatus.AWAITING_INPUT,
                key="clarify",
                workflow_data={**task.workflow_data, "input_pending": True},
            )
            return "pause"
        language = task.workflow_data["response_language"]
        data = {
            **task.workflow_data,
            "extraction": goal.model_dump(mode="json"),
            "input_pending": True,
        }
        data.pop("intake_extraction", None)
        if result.get("planner_error"):
            task = task.with_updates(
                events=(
                    *task.events,
                    TaskEvent(kind="planner_error", message=say("planner_unavailable", language)),
                )
            )
        if goal.offer_message and goal.offer_message not in task.workflow_data["planning_request"]:
            self._save(
                context, task, status=TaskStatus.AWAITING_INPUT, key="offer", workflow_data=data
            )
            return "pause"
        if goal.intent == Intent.UNKNOWN or goal.needs_clarification:
            self._save(
                context,
                task,
                status=TaskStatus.AWAITING_INPUT,
                key="planner_unavailable" if result.get("planner_error") else "clarify",
                workflow_data=data,
            )
            return "pause"
        if goal.intent == Intent.WIN_BACK and goal.offer_message is None:
            self._save(
                context,
                task,
                status=TaskStatus.AWAITING_INPUT,
                key="offer",
                intent=goal.intent,
                workflow_data=data,
            )
            return "pause"
        name, inputs = {
            Intent.SETTLEMENT: ("reconcile_settlement", {}),
            Intent.WIN_BACK: (
                "segment_inactive_customers",
                {"inactivity_days": goal.inactivity_days},
            ),
            Intent.HANDOFF: (None, {}),
        }[goal.intent]
        plan = ()
        if name:
            self._validate_tool(context, goal.intent, name, inputs)
            plan = (
                PlanStep(
                    task_id=task.task_id,
                    merchant_id=context.merchant_id,
                    step_id="prepare",
                    tool_name=name,
                    inputs=inputs,
                ),
            )
        self._save(
            context,
            task,
            status=TaskStatus.READY,
            key="running",
            goal=goal.goal,
            intent=goal.intent,
            plan=plan,
            workflow_data={
                **data,
                "phase": "prepare",
                "input_pending": False,
                "approval_start": len(task.approvals),
            },
        )
        return "continue"

    def _validate_tool(self, context, intent, name, inputs):
        available = {tool.metadata.name for tool in self.registry.discover(context, intent=intent)}
        if name not in available:
            raise CapabilityUnavailable(
                name,
                reason="missing_capability"
                if name not in self.registry._tools
                else "permission_denied",
            )
        self.registry._prepare(name, context, inputs)

    def _prepare(self, context, task):
        if task.status == TaskStatus.READY:
            task = self._save(context, task, status=TaskStatus.RUNNING, key="running")
        if task.status != TaskStatus.RUNNING:
            raise ActionConflict("Task must be running preparation")
        data = dict(task.workflow_data)
        evidence = task.evidence
        gaps = task.capability_gaps
        if task.intent == Intent.SETTLEMENT:
            try:
                proof = self.recovery.read(context, task.task_id, "reconcile_settlement", {})
            except RecoveryExhausted:
                self.recovery.event(context, task.task_id, "fallback_selected", "fallback")
                records = tuple(
                    record
                    for name in (
                        "get_transactions",
                        "get_refunds_and_chargebacks",
                        "get_bank_credits",
                    )
                    for record in self.recovery.read(context, task.task_id, name, {}).records
                )
                proof = reconcile_settlement(
                    context,
                    SettlementReport(records=records, captured_at=self.services.clock(context)),
                )
            proof = SettlementProof.model_validate(proof)
            data["settlement_proof"] = proof.model_dump(mode="json")
            data["settlement"] = InvestigationState(
                request=InvestigationRequest(
                    client_request_id=task.task_id,
                    message=task.original_request,
                    conversation_id=task.conversation_id,
                    settlement_reference=proof.settlement_reference,
                ),
                phase="approval",
                proof=proof,
            ).model_dump(mode="json")
            evidence = tuple(
                self.services._evidence(context, task.task_id, record) for record in proof.sources
            )
            task = self.recovery.task(context, task.task_id)
            data = {**task.workflow_data, **data}
            # Keep read budgets/results saved during preparation, even if later evidence fails.
            data.update(
                {
                    k: task.workflow_data[k]
                    for k in ("read_results", "read_attempts")
                    if k in task.workflow_data
                }
            )
            task = self._save(context, task, workflow_data=data, evidence=evidence)
            if proof.status != "complete" or proof.residual.amount_paise <= 0:
                raise RecoveryExhausted("Evidence cannot justify a shortfall case")
            data["approval_summary"] = say(
                "settlement_summary",
                data["response_language"],
                expected=rupees(proof.expected.amount_paise),
                credit=rupees(proof.credit.amount_paise),
                gap=rupees(proof.residual.amount_paise),
            )
            action = "create_support_ticket"
            inputs = {
                "task_id": task.task_id,
                "summary": (
                    f"Settlement {proof.settlement_reference}: "
                    f"expected {proof.expected.amount_paise} "
                    f"paise, credit {proof.credit.amount_paise} paise, "
                    f"gap {proof.residual.amount_paise} "
                    "paise. Sources: " + ", ".join(r.reference for r in proof.sources)
                ),
            }
        elif task.intent == Intent.WIN_BACK:
            segment = self.recovery.read(
                context,
                task.task_id,
                "segment_inactive_customers",
                {"inactivity_days": data["extraction"]["inactivity_days"]},
            )
            task = self.recovery.task(context, task.task_id)
            data = {**task.workflow_data, "segment": segment.model_dump(mode="json")}
            task = self._save(context, task, workflow_data=data)
            if not segment.recipient_ids:
                raise RecoveryExhausted("No eligible consenting customers")
            data["approval_summary"] = say(
                "campaign_summary",
                data["response_language"],
                count=segment.eligible_count,
                cost=rupees(segment.estimated_cost_paise),
                message=data["extraction"]["offer_message"],
            )
            action = "send_campaign"
            inputs = {
                "task_id": task.task_id,
                "message": data["extraction"]["offer_message"],
                "recipient_ids": list(segment.recipient_ids),
                "cost_paise": segment.estimated_cost_paise,
            }
        else:
            existing = data.get("handoff_draft", {})
            draft, gap = prepare_handoff(
                context,
                task,
                capability=existing.get("requested_capability", "bank_account_change"),
                reason=existing.get("reason", "missing_capability"),
            )
            gaps = (
                task.capability_gaps
                if gap in task.capability_gaps
                else (*task.capability_gaps, gap)
            )
            data.update(
                handoff_draft=draft.model_dump(mode="json"),
                handoff_explanation=say("handoff_limit", data["response_language"]),
            )
            task = self._save(
                context,
                task,
                capability_gaps=gaps,
                workflow_data=data,
                events=(
                    *task.events,
                    TaskEvent(kind="handoff_drafted", message=data["handoff_explanation"]),
                ),
            )
            action = "create_support_ticket"
            inputs = {"task_id": task.task_id, "summary": draft.summary}
        if task.intent == Intent.SETTLEMENT:
            state = InvestigationState.model_validate(data["settlement"])
            data["settlement"] = state.with_updates(case_summary=inputs["summary"]).model_dump(
                mode="json"
            )
        self._validate_tool(context, task.intent, action, inputs)
        definition, parsed = self.registry._prepare(action, context, inputs)
        verifier = definition.metadata.verification.tool_name
        plan = tuple(step.with_updates(status="done") for step in task.plan)
        plan += (
            PlanStep(
                task_id=task.task_id,
                merchant_id=context.merchant_id,
                step_id="action",
                tool_name=action,
                inputs=parsed.model_dump(mode="json"),
                dependencies=("prepare",) if plan else (),
            ),
        )
        # The reference is filled only from a provider receipt before dispatching verification.
        plan += (
            PlanStep(
                task_id=task.task_id,
                merchant_id=context.merchant_id,
                step_id="verify",
                tool_name=verifier,
                dependencies=("action",),
            ),
        )
        self._save(
            context,
            task,
            key="approval",
            plan=plan,
            evidence=evidence,
            capability_gaps=gaps,
            workflow_data={**data, "phase": "action"},
        )
        return "continue"

    def _approval_prompt(self, context, task):
        data = task.workflow_data
        language = data["response_language"]
        summary = ""
        if task.intent == Intent.SETTLEMENT:
            proof = data["settlement_proof"]
            summary = say(
                "settlement_summary",
                language,
                expected=rupees(proof["expected"]["amount_paise"]),
                credit=rupees(proof["credit"]["amount_paise"]),
                gap=rupees(proof["residual"]["amount_paise"]),
            )
        elif task.intent == Intent.WIN_BACK:
            segment = data["segment"]
            summary = say(
                "campaign_summary",
                language,
                count=segment["eligible_count"],
                cost=rupees(segment["estimated_cost_paise"]),
                message=data["extraction"]["offer_message"],
            )
        if task.intent == Intent.HANDOFF:
            summary = say("handoff_limit", language)
        self._save(
            context,
            task,
            next_action=(summary + "\n" + say("approval", language)).strip(),
            workflow_data={**data, "approval_summary": summary},
        )

    def _action(self, context, task):
        current = task.approvals[task.workflow_data.get("approval_start", 0) :]
        approval = current[-1] if current else None
        if approval is None:
            step = next(s for s in task.plan if s.step_id == "action")
            self.engine.request(context, task.task_id, step.tool_name, step.inputs)
            task = self.recovery.task(context, task.task_id)
            self._approval_prompt(context, task)
            return "pause"
        if approval.decision == "pending":
            self._approval_prompt(context, task)
            return "pause"
        if approval.decision == "cancelled":
            self._save(
                context,
                task,
                status=TaskStatus.AWAITING_INPUT,
                key="cancelled",
                workflow_data={**task.workflow_data, "phase": "plan", "input_pending": True},
            )
            return "pause"
        if task.has_unresolved_execution:
            self.recovery.inspect_write(context, task.task_id, approval)
        elif not any(r.idempotency_key for r in task.receipts):
            try:
                self.engine.execute(
                    context, task.task_id, approval.approval_id, approval.approved_inputs
                )
            except ActionConflict:
                task = self.recovery.task(context, task.task_id)
                if not task.has_unresolved_execution:
                    raise
                self.recovery.inspect_write(context, task.task_id, approval)
        task = self.recovery.task(context, task.task_id)
        if task.status != TaskStatus.VERIFYING:
            raise ActionConflict("Action has no verifiable receipt")
        self._save(
            context,
            task,
            key="running",
            workflow_data={**task.workflow_data, "phase": "verify"},
            plan=tuple(
                s.with_updates(status="done") if s.step_id == "action" else s for s in task.plan
            ),
        )
        return "continue"

    def _verify(self, context, task):
        receipt = task.receipts[-1]
        step = next(s for s in task.plan if s.step_id == "verify")
        result = self.recovery.read(
            context, task.task_id, step.tool_name, {"reference": receipt.external_reference}
        )
        if (
            not isinstance(result, VerificationResult)
            or not result.verified
            or result.task_id != task.task_id
            or result.merchant_id != context.merchant_id
            or result.external_reference != receipt.external_reference
        ):
            raise RecoveryExhausted("Independent evidence did not verify the action")
        # Persist the registry-validated independent read without another provider call.

        task = self.recovery.task(context, task.task_id)
        verification = Verification(
            task_id=task.task_id,
            merchant_id=context.merchant_id,
            verification_id=new_id(),
            receipt_id=receipt.receipt_id,
            tool_name=step.tool_name,
            verified=True,
            evidence_reference=result.evidence_reference,
        )
        task = self._save(
            context,
            task,
            verifications=(*task.verifications, verification),
            plan=tuple(
                s.with_updates(status="done", inputs={"reference": receipt.external_reference})
                if s.step_id == "verify"
                else s
                for s in task.plan
            ),
            workflow_data={
                **task.workflow_data,
                "phase": "finalize",
                "verification_result": result.model_dump(mode="json"),
            },
        )
        return "continue"

    def _finalize(self, context, task):
        result = task.workflow_data["verification_result"]
        receipt = task.receipts[-1]
        task = task.with_updates(workflow_data={**task.workflow_data, "phase": "finished"})
        if task.intent == Intent.SETTLEMENT:
            SettlementInvestigation(self.repo, self.services, self.registry).schedule(context, task)
            return "pause"
        if task.intent == Intent.HANDOFF:
            self._save(
                context,
                task,
                status=TaskStatus.ESCALATED,
                key="handoff"
                if task.workflow_data["handoff_draft"]["requested_capability"]
                == "bank_account_change"
                else "handoff_generic",
                capability_gaps=tuple(
                    g.with_updates(handoff_reference=receipt.external_reference)
                    for g in task.capability_gaps
                ),
            )
        else:
            self._save(
                context,
                task,
                status=TaskStatus.COMPLETED,
                next_action=say(
                    "campaign_done",
                    task.workflow_data["response_language"],
                    delivered=result["delivered"],
                    failed=result["failed"],
                ),
            )
        return "end"
