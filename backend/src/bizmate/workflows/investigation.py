import hashlib
from datetime import timedelta
from typing import Literal

from pydantic import AwareDatetime

from bizmate.agents.languages import say
from bizmate.domain.context import require_context
from bizmate.domain.lifecycle import transition_task
from bizmate.domain.models import (
    Intent,
    Model,
    PlanStep,
    Scope,
    SettlementResolution,
    Task,
    TaskEvent,
    TaskStatus,
)
from bizmate.domain.types import Identifier, MessageText
from bizmate.persistence.repository import TaskConflictError
from bizmate.services.mock_store import MockTimeout
from bizmate.tools.policy import ActionConflict, ActionNotFound, ApprovalEngine
from bizmate.workflows.settlement import (
    ReconciliationRequest,
    SettlementProof,
    reconcile_settlement,
)

S = TaskStatus


class InvestigationRequest(ReconciliationRequest):
    client_request_id: Identifier
    message: MessageText = "Why is my settlement short?"
    conversation_id: Identifier | None = None


class InvestigationState(Model):
    request: InvestigationRequest
    phase: Literal["investigate", "approval", "follow_up", "resolved", "stopped"] = "investigate"
    proof: SettlementProof | None = None
    case_summary: MessageText | None = None
    approval_id: Identifier | None = None
    receipt_id: Identifier | None = None
    report_attempts: int = 0
    follow_up_attempts: int = 0
    claim_until: AwareDatetime | None = None


class InvestigationView(Model):
    task: Task
    state: InvestigationState
    resolution: SettlementResolution | None = None


def state_of(task):
    return InvestigationState.model_validate(task.workflow_data["settlement"])


def with_state(task, state):
    return task.with_updates(
        workflow_data={**task.workflow_data, "settlement": state.model_dump(mode="json")}
    )


def event(task, kind, message):
    return task.with_updates(events=(*task.events, TaskEvent(kind=kind, message=message)))


class SettlementInvestigation:
    def __init__(self, repo, services, registry):
        self.repo, self.services, self.registry = repo, services, registry
        self.approvals = ApprovalEngine(repo, registry)

    def require(self, context):
        require_context(context)
        context.require(
            Scope.TASKS_READ, Scope.TASKS_WRITE, Scope.PAYMENTS_READ, Scope.TICKETS_WRITE
        )

    def get(self, context, task_id):
        require_context(context)
        context.require(Scope.TASKS_READ)
        task = self.repo.get_task(context, task_id)
        if task is None or "settlement" not in task.workflow_data:
            raise ActionNotFound("Settlement investigation not found")
        return task

    def view(self, context, task_id):
        task = self.get(context, task_id)
        resolution = task.workflow_data.get("settlement_resolution")
        return InvestigationView(
            task=task,
            state=state_of(task),
            resolution=SettlementResolution.model_validate(resolution) if resolution else None,
        )

    def start(self, context, body):
        self.require(context)
        body = InvestigationRequest.model_validate(body)
        task_id = (
            "settlement-"
            + hashlib.sha256(
                f"{context.merchant_id}:{body.client_request_id}".encode()
            ).hexdigest()[:40]
        )
        existing = self.repo.get_task(context, task_id)
        if existing:
            if state_of(existing).request != body:
                raise ActionConflict("Request ID is already bound to a different investigation")
            return existing
        state = InvestigationState(request=body)
        task = with_state(
            Task(
                task_id=task_id,
                merchant_id=context.merchant_id,
                conversation_id=body.conversation_id,
                goal=body.message.strip()[:200],
                original_request=body.message,
                intent=Intent.SETTLEMENT,
                next_action="Retrieve settlement evidence.",
                schedule_clock="demo",
                events=(
                    TaskEvent(
                        kind="investigation_started",
                        message="Synthetic settlement investigation started.",
                    ),
                ),
            ),
            state,
        )
        try:
            task = self.repo.save(context, task)
        except TaskConflictError:
            existing = self.get(context, task_id)
            if state_of(existing).request != body:
                raise ActionConflict("Request ID is bound to a different investigation") from None
            return existing
        return self.resume(context, task.task_id)

    def resume(self, context, task_id):
        self.require(context)
        task = self.get(context, task_id)
        state = state_of(task)
        if task.status in {S.COMPLETED, S.ESCALATED, S.FAILED} or state.phase == "follow_up":
            return task
        if state.phase == "investigate":
            if task.status == S.CREATED:
                task = self.repo.save(
                    context, transition_task(task, S.PLANNING, "Retrieve source evidence.")
                )
            proof = None
            while state.report_attempts < 3:
                state = state.with_updates(report_attempts=state.report_attempts + 1)
                task = self.repo.save(context, with_state(task, state))
                try:
                    proof = self.registry.execute(
                        "reconcile_settlement",
                        context,
                        {"settlement_reference": state.request.settlement_reference},
                    )
                    break
                except MockTimeout:
                    task = event(
                        task,
                        "report_timeout",
                        f"Settlement report timed out (attempt {state.report_attempts}/3).",
                    )
                    task = self.repo.save(context, task)
            if proof is None:
                task = self.repo.save(
                    context,
                    event(
                        task,
                        "ledger_fallback",
                        "Report retries exhausted. Reading available ledger sources instead.",
                    ),
                )
                try:
                    report = self.services.ledger_report(context).with_updates(
                        settlement_reference=state.request.settlement_reference
                    )
                    proof = reconcile_settlement(context, report)
                except MockTimeout:
                    return self.stop(
                        context,
                        task,
                        "Source reads remain unavailable; investigation needs review.",
                    )
            state = state.with_updates(proof=proof)
            task = with_state(task, state)
            if proof.status != "complete":
                return self.stop(
                    context,
                    task,
                    "Evidence is missing or conflicting. No confident gap or ticket was produced.",
                )
            if proof.residual.amount_paise <= 0:
                task = with_state(task, state.with_updates(phase="stopped"))
                return self.repo.save(
                    context,
                    transition_task(
                        task,
                        S.AWAITING_INPUT,
                        "No positive shortfall found. Clarify what needs investigation.",
                    ),
                )
            summary = (
                f"Synthetic settlement {proof.settlement_reference}. "
                f"Expected {proof.expected.amount_paise} paise; "
                f"credited {proof.credit.amount_paise} paise; "
                f"unexplained {proof.residual.amount_paise} paise. "
                f"Please investigate. Proof is saved on task {task_id}. Sources: "
                + ", ".join(r.reference for r in proof.sources[:20])
            )
            state = state.with_updates(case_summary=summary, phase="approval")
            evidence = tuple(self.services._evidence(context, task_id, r) for r in proof.sources)
            task = with_state(
                task.with_updates(
                    evidence=evidence,
                    plan=tuple(
                        PlanStep(
                            task_id=task_id,
                            merchant_id=context.merchant_id,
                            step_id=name,
                            tool_name=tool,
                            status="done" if name == "proof" else "pending",
                            dependencies=() if name == "proof" else (previous,),
                        )
                        for name, tool, previous in [
                            ("proof", "reconcile_settlement", ""),
                            ("ticket", "create_support_ticket", "proof"),
                            ("ticket_read", "get_ticket_status", "ticket"),
                            ("credit", "get_settlement_follow_up", "ticket_read"),
                        ]
                    ),
                ),
                state,
            )
            task = self.repo.save(
                context,
                transition_task(
                    task,
                    S.READY,
                    "Review the source-linked shortfall and support case before approving.",
                ),
            )
        if state.phase != "approval":
            return task
        if state.approval_id is None:
            # Recover an existing approval after interruption; never create a second case.
            pending = next((a for a in task.approvals if a.action == "create_support_ticket"), None)
            if pending is None:
                pending = self.approvals.request(
                    context,
                    task_id,
                    "create_support_ticket",
                    {"task_id": task_id, "summary": state.case_summary},
                )
            task = self.get(context, task_id)
            state = state.with_updates(approval_id=pending.approval_id)
            task = self.repo.save(context, with_state(task, state))
        approval = next(a for a in task.approvals if a.approval_id == state.approval_id)
        if approval.decision != "approved":
            return task
        receipt = next(
            (
                r
                for r in task.receipts
                if r.action == "create_support_ticket" and r.input_hash == approval.input_hash
            ),
            None,
        )
        if receipt is None:
            # An unresolved claim is never retried by the workflow.
            receipt = self.approvals.execute(
                context, task_id, approval.approval_id, approval.approved_inputs
            )
        task = self.get(context, task_id)
        if task.status != S.VERIFYING:
            return task
        self.approvals.verify(context, task_id, receipt.receipt_id)
        task = self.get(context, task_id)
        latest = [v for v in task.verifications if v.receipt_id == receipt.receipt_id]
        if not latest[-1].verified:
            return task
        return self.schedule(context, task)

    def schedule(self, context, task):
        state = state_of(task)
        receipt = task.receipts[-1]
        approval = next(a for a in task.approvals if a.input_hash == receipt.input_hash)
        state = state.with_updates(
            receipt_id=receipt.receipt_id, approval_id=approval.approval_id, phase="follow_up"
        )
        plan = tuple(
            p.with_updates(status="done") if p.step_id != "credit" else p for p in task.plan
        )
        if not any(p.step_id == "credit" for p in plan):
            plan += (
                PlanStep(
                    task_id=task.task_id,
                    merchant_id=context.merchant_id,
                    step_id="credit",
                    tool_name="get_settlement_follow_up",
                    inputs={"task_id": task.task_id},
                    dependencies=(plan[-1].step_id,) if plan else (),
                ),
            )
        task = with_state(
            task.with_updates(
                plan=plan,
                schedule_clock="demo",
                next_run_at=self.services.clock(context) + timedelta(days=1),
            ),
            state,
        )
        language = task.workflow_data.get("response_language", "en")
        return self.repo.save(
            context, transition_task(task, S.WAITING_EXTERNAL, say("settlement_wait", language))
        )

    def stop(self, context, task, message):
        state = state_of(task).with_updates(phase="stopped", claim_until=None)
        task = with_state(
            task.with_updates(
                next_run_at=None,
                workflow_data={**task.workflow_data, "settlement_review_reason": message},
            ),
            state,
        )
        if task.workflow_data.get("response_language", "en") != "en":
            message = say("error", task.workflow_data["response_language"])
        return self.repo.save(context, transition_task(task, S.ESCALATED, message))

    def scan(self, context):
        self.require(context)
        proof = self.registry.execute("reconcile_settlement", context, {})
        if proof.status != "complete":
            raise ActionConflict(
                "Cannot scan for mismatches while evidence is incomplete or conflicting"
            )
        if proof.residual.amount_paise <= 0:
            return []
        existing = [
            t
            for t in self.repo.list_tasks(context)
            if "settlement" in t.workflow_data
            and state_of(t).request.settlement_reference == proof.settlement_reference
        ]
        if existing:
            return existing
        key = "alert-" + proof.settlement_reference
        task = self.start(
            context,
            InvestigationRequest(
                client_request_id=key,
                settlement_reference=proof.settlement_reference,
                message="Proactive synthetic alert: investigate the settlement mismatch.",
            ),
        )
        return [task]
