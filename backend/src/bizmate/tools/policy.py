import hashlib
import inspect
import json

from bizmate.domain.context import MerchantContext, require_context
from bizmate.domain.errors import AccessDenied
from bizmate.domain.lifecycle import transition_task
from bizmate.domain.models import (
    ActionResult,
    Approval,
    Receipt,
    Scope,
    TaskEvent,
    TaskStatus,
    ToolExecution,
    Verification,
    VerificationResult,
    new_id,
    now,
)
from bizmate.persistence.repository import TaskConflictError, TaskRepository
from bizmate.tools.registry import ToolRegistry


class ActionNotFound(LookupError):
    pass


class ActionConflict(TaskConflictError):
    pass


def input_hash(merchant_id, task_id, action, inputs):
    payload = json.dumps(
        [merchant_id, task_id, action, inputs],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def execution_key(approval):
    return hashlib.sha256(
        f"{approval.merchant_id}:{approval.task_id}:{approval.approval_id}".encode()
    ).hexdigest()


class ApprovalEngine:
    def __init__(self, repo: TaskRepository, registry: ToolRegistry):
        self.repo = repo
        self.registry = registry

    def _task(self, context, task_id):
        require_context(context)
        context.require(Scope.TASKS_READ, Scope.TASKS_WRITE)
        task = self.repo.get_task(context, task_id)
        if task is None:
            raise ActionNotFound("Task not found")
        context.require_owner(task.merchant_id)
        return task

    def _approval(self, task, approval_id):
        approval = next((a for a in task.approvals if a.approval_id == approval_id), None)
        if approval is None:
            raise ActionNotFound("Approval not found")
        return approval

    def _prepare(self, context, task, action, inputs):
        definition, parsed = self.registry._prepare(action, context, inputs)
        if definition.metadata.risk != "side_effect":
            raise ActionConflict("Only side effects require approval")
        if task.intent not in definition.metadata.intents:
            raise ActionConflict("Action does not match the task intent")
        if hasattr(parsed, "task_id") and parsed.task_id != task.task_id:
            raise ActionConflict("Action inputs must reference this task")
        if not issubclass(definition.output_schema, ActionResult):
            raise ActionConflict("Write adapters must return ActionResult")
        verifier = self.registry._tools[definition.metadata.verification.tool_name]
        if not issubclass(verifier.output_schema, VerificationResult):
            raise ActionConflict("Verification adapters must return VerificationResult")
        try:
            inspect.signature(definition.handler).bind(context, parsed, idempotency_key="key")
        except TypeError as exc:
            raise ActionConflict("Write adapters must accept a server idempotency_key") from exc
        return definition, parsed

    def request(
        self, context: MerchantContext, task_id: str, action: str, inputs: dict
    ) -> Approval:
        task = self._task(context, task_id)
        if task.has_unresolved_execution:
            raise ActionConflict(
                "Inspect the unresolved execution before requesting another action"
            )
        if task.status not in {TaskStatus.READY, TaskStatus.RUNNING}:
            raise ActionConflict("Task must be ready or running to request approval")
        if any(a.decision == "pending" for a in task.approvals):
            raise ActionConflict("Decide the pending approval first")
        definition, parsed = self._prepare(context, task, action, inputs)
        self.registry._check_preconditions(definition, context, parsed)
        snapshot = parsed.model_dump(mode="json")
        approval = Approval(
            approval_id=new_id(),
            task_id=task.task_id,
            merchant_id=context.merchant_id,
            action=action,
            approved_inputs=snapshot,
            input_hash=input_hash(context.merchant_id, task.task_id, action, snapshot),
        )
        task = task.with_updates(approvals=(*task.approvals, approval))
        self.repo.save(
            context,
            transition_task(
                task,
                TaskStatus.AWAITING_APPROVAL,
                "Review the exact action inputs before approving.",
            ),
        )
        return approval

    def decide(self, context, task_id, approval_id, decision, expected_hash) -> Approval:
        require_context(context)
        context.require(Scope.TASKS_APPROVE)
        task = self._task(context, task_id)
        approval = self._approval(task, approval_id)
        if decision not in {"approve", "cancel"}:
            raise ActionConflict("Invalid approval decision")
        if expected_hash != approval.input_hash:
            raise ActionConflict("Action inputs changed; reload the approval")
        target = "approved" if decision == "approve" else "cancelled"
        if approval.decision == target:
            return approval
        if approval.decision == "cancelled":
            raise ActionConflict("Cancelled actions require a new approval")
        if any(e.execution_id == execution_key(approval) for e in task.tool_executions):
            raise ActionConflict("Execution has already been claimed")
        if task.status not in {TaskStatus.AWAITING_APPROVAL, TaskStatus.READY}:
            raise ActionConflict("Task is not awaiting an approval decision")
        if target == "approved":
            definition, parsed = self._prepare(
                context, task, approval.action, approval.approved_inputs
            )
            self._match(approval, parsed.model_dump(mode="json"))
            self.registry._check_preconditions(definition, context, parsed)
        decided = approval.with_updates(
            decision=target, approver=context.actor_id, decided_at=now()
        )
        task = task.with_updates(
            approvals=tuple(decided if a.approval_id == approval_id else a for a in task.approvals),
            events=(
                *task.events,
                TaskEvent(
                    kind="approval_decided",
                    occurred_at=decided.decided_at,
                    message=f"Action {target} by {context.actor_id} (approval {approval_id}).",
                ),
            ),
        )
        target_status = TaskStatus.READY if target == "approved" else TaskStatus.PLANNING
        self.repo.save(
            context,
            transition_task(
                task,
                target_status,
                "Approved action is ready to execute."
                if target == "approved"
                else "Action cancelled. Review a new plan before requesting approval.",
            ),
        )
        return decided

    def _match(self, approval, inputs):
        if approval.approved_inputs != inputs or approval.input_hash != input_hash(
            approval.merchant_id, approval.task_id, approval.action, inputs
        ):
            raise ActionConflict("Inputs differ from the approved snapshot; request new approval")

    def execute(self, context, task_id, approval_id, inputs) -> Receipt:
        task = self._task(context, task_id)
        context.require(Scope.TASKS_APPROVE)
        approval = self._approval(task, approval_id)
        if approval.decision != "approved" or approval.approver != context.actor_id:
            raise AccessDenied("Execution requires this actor's exact approved action")
        definition, parsed = self._prepare(context, task, approval.action, inputs)
        self._match(approval, parsed.model_dump(mode="json"))
        key = execution_key(approval)
        previous = next((r for r in task.receipts if r.idempotency_key == key), None)
        if previous:
            return previous
        if any(e.execution_id == key for e in task.tool_executions):
            raise ActionConflict("Outcome unresolved. Inspect the external action before any retry")
        if task.status != TaskStatus.READY:
            raise ActionConflict("Task must be ready to execute")
        self.registry._check_preconditions(definition, context, parsed)
        claim = ToolExecution(
            execution_id=key,
            task_id=task_id,
            merchant_id=context.merchant_id,
            tool_name=approval.action,
            input_hash=approval.input_hash,
            outcome="uncertain",
            error="Execution claimed; awaiting a durable receipt.",
        )
        task = task.with_updates(tool_executions=(*task.tool_executions, claim))
        # CAS saves the claim before dispatch; competing workers cannot both invoke the handler.
        task = self.repo.save(
            context, transition_task(task, TaskStatus.RUNNING, "Executing the approved action.")
        )
        try:
            result = definition.handler(context, parsed, idempotency_key=key)
            result = self.registry._result(definition, context, result)
        except Exception:
            # A timeout or invalid response can follow a successful external write.
            self.repo.save(
                context,
                transition_task(
                    task,
                    TaskStatus.WAITING_EXTERNAL,
                    "Action outcome is uncertain. Inspect it before retrying; no repeat was sent.",
                ),
            )
            raise ActionConflict("Action outcome uncertain; inspection required") from None
        receipt = Receipt(
            receipt_id=new_id(),
            task_id=task_id,
            merchant_id=context.merchant_id,
            external_reference=result.external_reference,
            action=approval.action,
            idempotency_key=key,
            input_hash=approval.input_hash,
        )
        execution = ToolExecution(
            execution_id=new_id(),
            task_id=task_id,
            merchant_id=context.merchant_id,
            tool_name=approval.action,
            input_hash=approval.input_hash,
            outcome="succeeded",
        )
        task = task.with_updates(
            receipts=(*task.receipts, receipt), tool_executions=(*task.tool_executions, execution)
        )
        self.repo.save(
            context,
            transition_task(
                task,
                TaskStatus.VERIFYING,
                "Action recorded. Independently verify the external reference.",
            ),
        )
        return receipt

    def verify(self, context, task_id, receipt_id) -> Verification:
        task = self._task(context, task_id)
        receipt = next((r for r in task.receipts if r.receipt_id == receipt_id), None)
        if receipt is None:
            raise ActionNotFound("Receipt not found")
        if task.status != TaskStatus.VERIFYING:
            raise ActionConflict("Task must be verifying")
        definition = self.registry._tools.get(receipt.action)
        if definition is None or definition.metadata.verification is None:
            raise ActionConflict("Verification tool is not registered")
        spec = definition.metadata.verification
        verifier = self.registry._tools[spec.tool_name]
        context.require(*self.registry._required_scopes(verifier))
        verified, reference = False, "verification_unavailable"
        try:
            result = self.registry.execute(
                spec.tool_name, context, {"reference": receipt.external_reference}
            )
            if isinstance(result, VerificationResult):
                verified = (
                    result.verified
                    and result.merchant_id == context.merchant_id
                    and result.task_id == task_id
                    and result.external_reference == receipt.external_reference
                )
                reference = result.evidence_reference
        except Exception:
            pass
        verification = Verification(
            verification_id=new_id(),
            receipt_id=receipt_id,
            task_id=task_id,
            merchant_id=context.merchant_id,
            tool_name=spec.tool_name,
            verified=verified,
            evidence_reference=reference,
        )
        self.repo.save(
            context,
            task.with_updates(
                verifications=(*task.verifications, verification),
                events=(
                    *task.events,
                    TaskEvent(
                        kind="action_verified" if verified else "verification_failed",
                        message="Independent action verification passed."
                        if verified
                        else "Action verification failed. The task remains unresolved.",
                    ),
                ),
                next_action="Action verified. Continue checking the task goal."
                if verified
                else "Verification failed. Inspect the action; the task remains unresolved.",
            ),
        )
        return verification
