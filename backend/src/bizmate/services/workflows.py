from datetime import timedelta

from bizmate.domain.models import (
    Approval,
    CapabilityGap,
    Evidence,
    Intent,
    Merchant,
    Model,
    Receipt,
    Task,
    TaskEvent,
    TaskStatus,
    ToolExecution,
    Verification,
    new_id,
)
from bizmate.persistence.repository import TaskConflictError, TaskRepository
from bizmate.services.demo import MERCHANTS
from bizmate.services.mocks import MockServices, MockTimeout, action_hash
from bizmate.services.models import (
    CampaignDraft,
    CampaignInputs,
    HandoffDraft,
    Segment,
    SettlementFollowup,
    TicketInputs,
)
from bizmate.tools.policy import validate_approved_action
from bizmate.tools.registry import ToolMetadata, ToolRegistry
from bizmate.workflows.campaign import segment_inactive_customers
from bizmate.workflows.handoff import prepare_handoff
from bizmate.workflows.settlement import reconcile_settlement


class EmptyInputs(Model):
    pass


class ReferenceInputs(Model):
    reference: str


class WorkflowService:
    """Synthetic service workflows sharing persisted approvals, tools and verification rules."""

    def __init__(self, repo: TaskRepository, mocks: MockServices):
        self.repo = repo
        self.mocks = mocks
        self.registry = ToolRegistry()
        self._register_tools()

    def _register_tools(self):
        for name, scope, handler in [
            (
                "get_customers_and_orders",
                "customers:read",
                lambda merchant, inputs: self.mocks.customers_and_orders(merchant.merchant_id),
            ),
            (
                "get_settlement_report",
                "payments:read",
                lambda merchant, inputs: self.mocks.settlement(merchant.merchant_id),
            ),
        ]:
            self.registry.register(
                ToolMetadata(
                    name=name,
                    description=name.replace("_", " "),
                    category="synthetic",
                    risk="read",
                    required_scopes=[scope],
                ),
                EmptyInputs,
                handler,
            )
        for name, scope, schema, handler, verification in [
            (
                "create_support_ticket",
                "tickets:write",
                TicketInputs,
                lambda merchant, inputs: self.mocks.create(
                    merchant.merchant_id,
                    inputs,
                    self.action_key("create_support_ticket", inputs.model_dump()),
                ),
                "get_ticket_status",
            ),
            (
                "send_campaign",
                "campaigns:write",
                CampaignInputs,
                lambda merchant, inputs: self.mocks.send(
                    merchant.merchant_id,
                    inputs,
                    self.action_key("send_campaign", inputs.model_dump()),
                ),
                "get_campaign_delivery_status",
            ),
        ]:
            self.registry.register(
                ToolMetadata(
                    name=name,
                    description=f"Simulated {name}",
                    category="synthetic",
                    risk="side_effect",
                    required_scopes=[scope],
                    approval_required=True,
                    idempotency="task_and_input_hash",
                    verification_tool=verification,
                ),
                schema,
                handler,
            )
        for name, scope, handler in [
            (
                "get_ticket_status",
                "tickets:write",
                lambda merchant, inputs: self.mocks.status(merchant.merchant_id, inputs.reference),
            ),
            (
                "get_campaign_delivery_status",
                "campaigns:write",
                lambda merchant, inputs: self.mocks.delivery(
                    merchant.merchant_id, inputs.reference
                ),
            ),
        ]:
            self.registry.register(
                ToolMetadata(
                    name=name,
                    description=f"Independently read {name}",
                    category="verification",
                    risk="read",
                    required_scopes=[scope],
                ),
                ReferenceInputs,
                handler,
            )

    @staticmethod
    def action_key(action: str, inputs: dict) -> str:
        return f"{inputs['task_id']}:{action_hash(action, inputs)}"

    def owned_task(self, merchant: Merchant, task_id: str) -> Task:
        task = self.repo.get_task(merchant.merchant_id, task_id)
        if task is None:
            raise KeyError("Task not found")
        return task

    def event(self, task: Task, kind: str, message: str):
        task.events.append(
            TaskEvent(kind=kind, message=message, occurred_at=self.mocks.clock(task.merchant_id))
        )

    def segment(self, merchant: Merchant, inactivity_days: int = 30) -> Segment:
        customers, orders = self.registry.execute("get_customers_and_orders", merchant, {})
        return segment_inactive_customers(
            customers, orders, self.mocks.clock(merchant.merchant_id), inactivity_days
        )

    def _review(self, task: Task, action: str, inputs: dict) -> Task:
        current = self.mocks.clock(task.merchant_id)
        for approval in task.approvals:
            if approval.decision == "pending":
                approval.decision = "cancelled"
                approval.approver = task.merchant_id
                approval.decided_at = current
        task.approvals.append(
            Approval(
                approval_id=new_id(),
                task_id=task.task_id,
                merchant_id=task.merchant_id,
                action=action,
                approved_inputs=inputs,
                input_hash=action_hash(action, inputs),
            )
        )
        task.status = TaskStatus.AWAITING_APPROVAL
        task.next_run_at = None
        task.next_action = (
            "Review the exact action and approve or cancel. All actions are simulated."
        )
        self.event(task, "approval_requested", task.next_action)
        return self.repo.save(task)

    def draft_campaign(
        self, merchant: Merchant, draft: CampaignDraft, task_id: str | None = None
    ) -> Task:
        if "campaigns:write" not in merchant.scopes:
            raise PermissionError("Missing campaign permission")
        segment = self.segment(merchant, draft.inactivity_days)
        if not segment.recipient_ids:
            raise ValueError("There are no consenting inactive recipients for this window")
        if task_id is None:
            task = Task(
                merchant_id=merchant.merchant_id,
                goal="Review customer win-back campaign",
                original_request=draft.message,
                intent=Intent.WIN_BACK,
                next_action="Review campaign",
                created_at=self.mocks.clock(merchant.merchant_id),
            )
        else:
            task = self.owned_task(merchant, task_id)
            if task.intent != Intent.WIN_BACK or task.status not in (
                TaskStatus.AWAITING_APPROVAL,
                TaskStatus.AWAITING_INPUT,
            ):
                raise TaskConflictError(
                    "Campaign execution has started. Create a new campaign task."
                )
        task.workflow_data = {
            "type": "campaign",
            "segment": segment.model_dump(mode="json"),
            "message": draft.message,
            "delivery": None,
        }
        inputs = CampaignInputs(
            task_id=task.task_id,
            message=draft.message,
            recipient_ids=segment.recipient_ids,
            cost_paise=segment.cost_paise,
        )
        self.event(
            task,
            "campaign_review",
            f"{len(segment.recipient_ids)} eligible recipients. "
            f"Estimated cost {segment.cost_paise} paise. Simulated send.",
        )
        return self._review(task, "send_campaign", inputs.model_dump())

    def draft_handoff(self, merchant: Merchant, draft: HandoffDraft) -> Task:
        if "tickets:write" not in merchant.scopes:
            raise PermissionError("Missing support ticket permission")
        gap = prepare_handoff(merchant, draft.requested_capability, self.registry)
        task = Task(
            merchant_id=merchant.merchant_id,
            goal="Request human-support assistance",
            original_request=draft.summary,
            intent=Intent.HANDOFF,
            next_action="Review support handoff",
            created_at=self.mocks.clock(merchant.merchant_id),
            workflow_data={"type": "handoff", "gap": gap.model_dump(mode="json")},
        )
        self.event(task, "capability_gap", gap.reason)
        task = self._review(
            task,
            "create_support_ticket",
            TicketInputs(task_id=task.task_id, summary=draft.summary).model_dump(),
        )
        self.mocks.record_gap(gap)
        return task

    def check_settlement(self, merchant: Merchant) -> Task | None:
        if "payments:read" not in merchant.scopes or "tickets:write" not in merchant.scopes:
            raise PermissionError(
                "Settlement follow-up requires payment read and support permissions"
            )
        task_id = f"settlement-followup-{merchant.merchant_id}-settlement-001"
        existing = self.repo.get_task(merchant.merchant_id, task_id)
        if existing is not None:
            return existing
        task = Task(
            task_id=task_id,
            merchant_id=merchant.merchant_id,
            goal="Follow up on a short settlement",
            original_request="Scheduled synthetic settlement mismatch check",
            intent=Intent.SETTLEMENT,
            next_action="Check settlement records",
            created_at=self.mocks.clock(merchant.merchant_id),
        )
        records = None
        for attempt in range(2):
            try:
                records = self.registry.execute("get_settlement_report", merchant, {})
                break
            except MockTimeout as exc:
                self.event(task, "read_timeout", str(exc))
                task.executions.append(
                    ToolExecution(
                        execution_id=new_id(),
                        task_id=task.task_id,
                        tool_name="get_settlement_report",
                        input_hash=action_hash("get_settlement_report", {}),
                        outcome="error",
                        error=str(exc),
                        occurred_at=self.mocks.clock(merchant.merchant_id),
                    )
                )
                self.event(task, "safe_read_retry", f"Read attempt {attempt + 1} of 2 failed.")
        if records is None:
            records = self.mocks.settlement(merchant.merchant_id, fallback=True)
            self.event(
                task,
                "fallback",
                "Used persisted synthetic source records after two report timeouts.",
            )
        proof = reconcile_settlement(records)
        if proof["residual_paise"] <= 0:
            return None
        followup = SettlementFollowup(
            settlement_reference=records.settlement_reference,
            outstanding_paise=proof["residual_paise"],
            baseline_credit_reference=records.bank_credit_reference,
            evidence_after=self.mocks.clock(merchant.merchant_id),
        )
        task.workflow_data = {
            "type": "settlement",
            "proof": proof,
            "followup": followup.model_dump(mode="json"),
        }
        for field, amount in records.model_dump().items():
            if field.endswith("_paise"):
                task.evidence.append(
                    Evidence(
                        evidence_id=f"{task.task_id}-{field}",
                        source="mock_settlement",
                        source_reference=records.settlement_reference,
                        description=field,
                        amount_paise=amount,
                        captured_at=self.mocks.clock(merchant.merchant_id),
                    )
                )
        self.event(
            task,
            "settlement_mismatch",
            f"Synthetic settlement has {proof['residual_paise']} paise outstanding.",
        )
        inputs = TicketInputs(
            task_id=task.task_id,
            summary=f"Investigate {proof['residual_paise']} paise "
            f"outstanding for {records.settlement_reference}. "
            f"Sources: {records.bank_credit_reference}.",
        )
        try:
            return self._review(task, "create_support_ticket", inputs.model_dump())
        except TaskConflictError:
            return self.owned_task(merchant, task_id)

    def decide(
        self, merchant: Merchant, task_id: str, approval_id: str, decision: str, input_hash: str
    ) -> Task:
        task = self.owned_task(merchant, task_id)
        approval = next((item for item in task.approvals if item.approval_id == approval_id), None)
        if approval is None:
            raise KeyError("Approval not found")
        if (
            approval.input_hash != input_hash
            or approval.merchant_id != merchant.merchant_id
            or approval.input_hash != action_hash(approval.action, approval.approved_inputs)
        ):
            raise TaskConflictError("The approval inputs changed. Reload the current review.")
        if approval.decision == "cancelled":
            if decision == "cancel":
                return task
            raise TaskConflictError("This approval was cancelled. Review the current action.")
        if approval.decision == "approved":
            if decision == "cancel":
                raise TaskConflictError(
                    "Execution already started. This approval cannot be cancelled."
                )
            return task
        if task.status != TaskStatus.AWAITING_APPROVAL:
            raise TaskConflictError("Task is not awaiting approval")
        approval.approver = merchant.merchant_id
        approval.decided_at = self.mocks.clock(merchant.merchant_id)
        if decision == "cancel":
            approval.decision = "cancelled"
            task.status = TaskStatus.AWAITING_INPUT
            task.next_action = "Action cancelled. Edit the review or start another task."
            self.event(task, "approval_cancelled", task.next_action)
            return self.repo.save(task)
        if approval.action == "send_campaign":
            eligible = self.segment(merchant, task.workflow_data["segment"]["inactivity_days"])
            if not set(approval.approved_inputs["recipient_ids"]) <= set(eligible.recipient_ids):
                approval.decision = "cancelled"
                task.status = TaskStatus.AWAITING_INPUT
                task.next_action = (
                    "Audience eligibility changed. Review and approve a new campaign snapshot."
                )
                self.event(task, "review_required", task.next_action)
                self.repo.save(task)
                raise TaskConflictError(task.next_action)
        approval.decision = "approved"
        task.status = TaskStatus.RUNNING
        task.next_action = "Execute the approved simulated action and verify it independently."
        # A due time allows startup recovery if the process stops before recording the write result.
        task.next_run_at = self.mocks.clock(merchant.merchant_id)
        self.event(task, "approval_recorded", "Merchant approved the exact action inputs.")
        task = self.repo.save(task)
        return self.execute(task, merchant)

    def _pause(self, task: Task, exc: Exception, tool: str) -> Task:
        task.status = TaskStatus.WAITING_EXTERNAL
        task.next_run_at = self.mocks.clock(task.merchant_id) + timedelta(seconds=60)
        task.next_action = "Inspect the action, then retry its independent verification."
        task.executions.append(
            ToolExecution(
                execution_id=new_id(),
                task_id=task.task_id,
                tool_name=tool,
                input_hash=task.approvals[-1].input_hash,
                outcome="error",
                error=str(exc),
                occurred_at=self.mocks.clock(task.merchant_id),
            )
        )
        self.event(task, "service_timeout", str(exc))
        return self.repo.save(task)

    def execute(self, task: Task, merchant: Merchant) -> Task:
        approval = task.approvals[-1]
        inputs = approval.approved_inputs
        validate_approved_action(approval, merchant, approval.action, inputs)
        key = self.action_key(approval.action, inputs)
        try:
            # Inspect durable provider state before retrying any uncertain side effect.
            receipt = self.mocks.find_action(merchant.merchant_id, approval.action, key)
            if receipt is None:
                receipt = self.registry.execute(
                    approval.action, merchant, inputs, approval=approval
                )
            if receipt.task_id != task.task_id or receipt.input_hash != approval.input_hash:
                raise ValueError("Receipt does not match the approved task inputs")
            if not any(item.receipt_id == receipt.receipt_id for item in task.receipts):
                task.receipts.append(receipt)
                self.event(
                    task,
                    "action_receipt",
                    f"Simulated action recorded as {receipt.external_reference}.",
                )
            task.status = TaskStatus.VERIFYING
            task = self.repo.save(task)
        except MockTimeout as exc:
            return self._pause(task, exc, approval.action)
        except (ValueError, PermissionError) as exc:
            task.status = TaskStatus.AWAITING_INPUT
            task.next_run_at = None
            task.next_action = str(exc)
            task.approvals[-1].decision = "cancelled"
            self.event(task, "review_required", str(exc))
            return self.repo.save(task)
        return self.verify(task, merchant, receipt)

    def verify(self, task: Task, merchant: Merchant, receipt: Receipt) -> Task:
        is_campaign = task.workflow_data["type"] == "campaign"
        tool = "get_campaign_delivery_status" if is_campaign else "get_ticket_status"
        try:
            result = self.registry.execute(
                tool, merchant, {"reference": receipt.external_reference}
            )
            if is_campaign:
                approved_count = len(task.approvals[-1].approved_inputs["recipient_ids"])
                if (
                    result.get("delivered", -1) < 0
                    or result.get("failed", -1) < 0
                    or result["delivered"] + result["failed"] != approved_count
                ):
                    raise ValueError("Delivery counts conflict with the approved audience")
                task.workflow_data["delivery"] = result
                task.status = TaskStatus.COMPLETED
                task.next_action = (
                    f"Simulated delivery verified: {result['delivered']} delivered, "
                    f"{result['failed']} failed."
                )
                task.next_run_at = None
            elif result != "open":
                raise ValueError("The independent support read did not confirm the ticket")
            elif task.workflow_data["type"] == "handoff":
                task.status = TaskStatus.ESCALATED
                task.next_action = (
                    "Support ticket verified. The requested account change "
                    "remains pending with human support."
                )
                task.next_run_at = None
                gap = CapabilityGap.model_validate(task.workflow_data["gap"])
                gap.handoff_reference = receipt.external_reference
                task.workflow_data["gap"] = gap.model_dump(mode="json")
                self.mocks.record_gap(gap)
            else:
                task.status = TaskStatus.WAITING_EXTERNAL
                task.next_run_at = self.mocks.clock(task.merchant_id) + timedelta(days=1)
                task.next_action = (
                    "Support ticket verified. Check fresh settlement credits at the scheduled time."
                )
            task.verifications.append(
                Verification(
                    verification_id=new_id(),
                    receipt_id=receipt.receipt_id,
                    tool_name=tool,
                    verified=True,
                    evidence_reference=receipt.external_reference,
                    verified_at=self.mocks.clock(task.merchant_id),
                )
            )
            self.event(task, "independent_verification", task.next_action)
            return self.repo.save(task)
        except (MockTimeout, KeyError, ValueError) as exc:
            task.verifications.append(
                Verification(
                    verification_id=new_id(),
                    receipt_id=receipt.receipt_id,
                    tool_name=tool,
                    verified=False,
                    evidence_reference=receipt.external_reference,
                    verified_at=self.mocks.clock(task.merchant_id),
                )
            )
            return self._pause(task, exc, tool)

    def recover_interrupted(self, merchant_id: str):
        for task in self.repo.list_tasks(merchant_id):
            if task.workflow_data.get("type") and task.status in (
                TaskStatus.RUNNING,
                TaskStatus.VERIFYING,
            ):
                task.status = TaskStatus.WAITING_EXTERNAL
                task.next_run_at = self.mocks.clock(merchant_id)
                self.event(
                    task,
                    "restart_recovery",
                    "Resuming from persisted approval and provider records.",
                )
                try:
                    self.repo.save(task)
                except TaskConflictError:
                    continue

    def resume_task(self, merchant_id: str, task_id: str) -> Task:
        merchant = MERCHANTS[merchant_id].model_copy(deep=True)
        task = self.owned_task(merchant, task_id)
        ticket_verified = any(
            item.verified and item.tool_name == "get_ticket_status" for item in task.verifications
        )
        if task.workflow_data.get("type") == "settlement" and ticket_verified:
            return self.verify_credit(task)
        return self.execute(task, merchant)

    def verify_credit(self, task: Task) -> Task:
        followup = SettlementFollowup.model_validate(task.workflow_data["followup"])
        try:
            credits = self.mocks.fresh_credits(task.merchant_id, followup.baseline_credit_reference)
        except (MockTimeout, ValueError) as exc:
            return self._pause(task, exc, "fresh_credits")
        matches = [
            credit
            for credit in credits
            if credit.settlement_reference == followup.settlement_reference
            and credit.amount_paise == followup.outstanding_paise
            and credit.available_at > followup.evidence_after
            and credit.reference != followup.baseline_credit_reference
        ]
        if len(matches) == 1 and len(credits) == 1:
            credit = matches[0]
            task.evidence.append(
                Evidence(
                    evidence_id=f"fresh-{credit.reference}",
                    source="mock_bank_credit",
                    source_reference=credit.reference,
                    description="Fresh matching outstanding settlement credit",
                    amount_paise=credit.amount_paise,
                    captured_at=credit.available_at,
                )
            )
            task.verifications.append(
                Verification(
                    verification_id=new_id(),
                    receipt_id=task.receipts[-1].receipt_id,
                    tool_name="fresh_credits",
                    verified=True,
                    evidence_reference=credit.reference,
                    verified_at=self.mocks.clock(task.merchant_id),
                )
            )
            task.status = TaskStatus.COMPLETED
            task.next_action = (
                f"Fresh credit of {credit.amount_paise} paise verified. Settlement gap resolved."
            )
            task.next_run_at = None
            self.event(task, "settlement_resolved", task.next_action)
        else:
            task.status = TaskStatus.WAITING_EXTERNAL
            task.next_run_at = self.mocks.clock(task.merchant_id) + timedelta(days=1)
            task.next_action = (
                "Fresh matching credit is missing or conflicting. The settlement remains open."
            )
            self.event(task, "settlement_pending", task.next_action)
        return self.repo.save(task)
