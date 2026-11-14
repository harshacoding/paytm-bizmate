"""Durable read budgets and inspection-only recovery of uncertain writes."""

import json

from bizmate.agents.languages import say
from bizmate.domain.context import require_context
from bizmate.domain.errors import AccessDenied
from bizmate.domain.lifecycle import transition_task
from bizmate.domain.models import Receipt, Scope, TaskEvent, TaskStatus, ToolExecution, new_id
from bizmate.services.mocks import input_hash as provider_hash
from bizmate.tools.policy import ActionConflict, execution_key, input_hash


class RecoveryExhausted(Exception):
    pass


class Recovery:
    MAX_READ_ATTEMPTS = 3

    def __init__(self, repo, registry, services):
        self.repo, self.registry, self.services = repo, registry, services

    def task(self, context, task_id):
        require_context(context)
        context.require(Scope.TASKS_READ, Scope.TASKS_WRITE)
        task = self.repo.get_task(context, task_id)
        if task is None:
            raise ActionConflict("Task not found")
        context.require_owner(task.merchant_id)
        return task

    def event(self, context, task_id, kind, key, **data):
        task = self.task(context, task_id)
        language = task.workflow_data.get("response_language", "en")
        return self.repo.save(
            context,
            task.with_updates(
                workflow_data={**task.workflow_data, **data},
                events=(*task.events, TaskEvent(kind=kind, message=say(key, language))),
            ),
        )

    def read(self, context, task_id, name, inputs):
        task = self.task(context, task_id)
        definition, _ = self.registry._prepare(name, context, inputs)
        if (
            definition.metadata.risk not in {"read", "preparation"}
            or definition.metadata.idempotency != "safe_retry"
            or task.intent not in definition.metadata.intents
        ):
            raise AccessDenied("Recovery only dispatches relevant safe reads/preparation")
        generation = task.workflow_data.get("read_generation", 0)
        hash_inputs = {"generation": generation, "inputs": inputs} if generation else inputs
        key = input_hash(context.merchant_id, task_id, name, hash_inputs)
        cache = task.workflow_data.get("read_results", {})
        if key in cache:
            result = definition.output_schema.model_validate_json(json.dumps(cache[key]))
            return self.registry._result(definition, context, result)
        while True:
            task = self.task(context, task_id)
            attempts = task.workflow_data.get("read_attempts", {})
            count = attempts.get(key, 0)
            if count >= self.MAX_READ_ATTEMPTS:
                raise RecoveryExhausted(f"Read budget exhausted for {name}")
            # Claim the attempt durably before dispatch. A crash also consumes its budget.
            task = self.repo.save(
                context,
                task.with_updates(
                    workflow_data={
                        **task.workflow_data,
                        "read_attempts": {**attempts, key: count + 1},
                    }
                ),
            )
            try:
                result = self.registry.execute(name, context, inputs)
            except (TimeoutError, ConnectionError):
                self._record(context, task_id, name, key, "failed", "Safe read timed out")
                self.event(context, task_id, "read_retry", "read_error")
                continue
            except Exception:
                self._record(context, task_id, name, key, "failed", "Read validation/policy failed")
                raise
            task = self.task(context, task_id)
            task = self.repo.save(
                context,
                task.with_updates(
                    workflow_data={
                        **task.workflow_data,
                        "read_results": {
                            **task.workflow_data.get("read_results", {}),
                            key: result.model_dump(mode="json"),
                        },
                    }
                ),
            )
            self._record(context, task_id, name, key, "succeeded")
            return result

    def _record(self, context, task_id, name, digest, outcome, error=None):
        task = self.task(context, task_id)
        record = ToolExecution(
            task_id=task_id,
            merchant_id=context.merchant_id,
            execution_id=new_id(),
            tool_name=name,
            input_hash=digest,
            outcome=outcome,
            error=error,
        )
        self.repo.save(context, task.with_updates(tool_executions=(*task.tool_executions, record)))

    def inspect_write(self, context, task_id, approval):
        task = self.task(context, task_id)
        context.require(Scope.TASKS_APPROVE)
        if approval.decision != "approved" or approval.approver != context.actor_id:
            raise AccessDenied("Inspection requires the action's approving actor")
        key = execution_key(approval)
        existing = next((r for r in task.receipts if r.idempotency_key == key), None)
        if existing:
            return existing
        claim = next((e for e in task.tool_executions if e.execution_id == key), None)
        if (
            claim is None
            or claim.outcome != "uncertain"
            or claim.input_hash != approval.input_hash
            or claim.tool_name != approval.action
        ):
            raise ActionConflict("No matching uncertain execution to inspect")
        # This path performs reads only. Absence never authorizes another write.
        provider_receipt = self.services.lookup(context, approval.action, key)
        if provider_receipt is None:
            raise RecoveryExhausted("Provider outcome remains unknown. Manual inspection required")
        row = self.services.store.action(
            context.merchant_id,
            approval.action,
            provider_receipt.external_reference,
        )
        observed = json.loads(row["inputs"])
        if (
            provider_receipt.merchant_id != context.merchant_id
            or provider_receipt.task_id != task_id
            or provider_receipt.action != approval.action
            or provider_receipt.idempotency_key != key
            or observed != approval.approved_inputs
            or row["task_id"] != task_id
            or row["idempotency_key"] != key
            or row["input_hash"] != provider_hash(approval.action, observed)
            or provider_receipt.input_hash != row["input_hash"]
            or input_hash(context.merchant_id, task_id, approval.action, observed)
            != approval.input_hash
        ):
            raise RecoveryExhausted("Provider evidence conflicts with the approved action")
        receipt = Receipt(
            receipt_id=new_id(),
            merchant_id=context.merchant_id,
            task_id=task_id,
            external_reference=provider_receipt.external_reference,
            action=approval.action,
            idempotency_key=key,
            input_hash=approval.input_hash,
        )
        task = self.task(context, task_id)
        task = task.with_updates(receipts=(*task.receipts, receipt))
        self.repo.save(
            context,
            transition_task(
                task,
                TaskStatus.VERIFYING,
                say("recovered", task.workflow_data["response_language"]),
            ),
        )
        self.event(context, task_id, "write_inspected", "recovered")
        return receipt
