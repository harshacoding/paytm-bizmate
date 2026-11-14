from datetime import timedelta

from bizmate.agents.languages import say
from bizmate.domain.context import require_context
from bizmate.domain.lifecycle import transition_task
from bizmate.domain.models import Scope, SettlementResolution, TaskStatus, now
from bizmate.persistence.repository import TaskConflictError
from bizmate.services.mock_models import SettlementReport
from bizmate.services.mock_store import MockTimeout
from bizmate.workflows.investigation import event, state_of, with_state
from bizmate.workflows.settlement import reconcile_settlement

S = TaskStatus


def run_due_tasks(workflow, context):
    """Scoped safe reads only; a durable lease plus task revision protects concurrent runners."""
    require_context(context)
    context.require(Scope.TASKS_READ, Scope.TASKS_WRITE, Scope.PAYMENTS_READ)
    results = []
    for task in workflow.repo.list_tasks(context):
        if "settlement" not in task.workflow_data:
            continue
        state = state_of(task)
        if state.phase == "resolved" and task.status == S.VERIFYING:
            try:
                results.append(_complete(workflow, context, task))
            except TaskConflictError:
                pass
            continue
        if state.phase != "follow_up" or task.next_run_at is None:
            continue
        if task.next_run_at > workflow.services.clock(context):
            continue
        if task.status == S.RUNNING:
            if state.claim_until and state.claim_until > now():
                continue
        elif task.status != S.WAITING_EXTERNAL:
            continue
        if state.follow_up_attempts >= 3:
            try:
                results.append(
                    workflow.stop(
                        context, task, "Follow-up attempt limit reached; human review required."
                    )
                )
            except TaskConflictError:
                pass
            continue
        state = state.with_updates(
            claim_until=now() + timedelta(seconds=30),
            follow_up_attempts=state.follow_up_attempts + 1,
        )
        claim = with_state(task, state)
        if task.status == S.WAITING_EXTERNAL:
            claim = transition_task(
                claim, S.RUNNING, say("running", task.workflow_data.get("response_language", "en"))
            )
        try:
            claim = workflow.repo.save(context, claim)
        except TaskConflictError:
            continue
        try:
            results.append(_check_credit(workflow, context, claim))
        except TaskConflictError:
            # Another state update wins; never repeat a write or overwrite a newer snapshot.
            continue
    return results


def _check_credit(workflow, context, task):
    state = state_of(task)
    proof = state.proof
    state = state.with_updates(claim_until=None)
    task = with_state(task, state)
    task = event(
        task, "follow_up_started", "Reading independent fresh-credit evidence (demo time)."
    )
    try:
        records = workflow.registry.execute(
            "get_settlement_follow_up", context, {"task_id": task.task_id}
        ).records
    except MockTimeout:
        return _wait(
            workflow, context, task, "Fresh-credit source timed out. No action was resent."
        )
    except (ValueError, KeyError):
        return workflow.stop(context, task, "Credit evidence is invalid. Human review required.")
    baseline = [r for r in proof.sources if r.kind == "credit"]
    available = {r.reference: r for r in records}
    if any(available.get(r.reference) != r for r in proof.sources):
        return workflow.stop(
            context,
            task,
            "Baseline evidence changed or disappeared. Review the conflicting evidence.",
        )
    old_refs = {r.reference for r in proof.sources}
    fresh = [
        r
        for r in records
        if r.kind == "credit"
        and r.settlement_reference == proof.settlement_reference
        and r.available_at > proof.captured_at
        and r.reference not in old_refs
    ]
    if not fresh:
        return _wait(
            workflow,
            context,
            task,
            "No fresh matching settlement credit yet. Investigation remains open.",
        )
    if len(fresh) != 1 or fresh[0].amount_paise != proof.residual.amount_paise:
        return workflow.stop(
            context,
            task,
            "Fresh credits conflict with the outstanding amount. Human review required.",
        )
    current = reconcile_settlement(
        context,
        SettlementReport(
            settlement_reference=proof.settlement_reference,
            records=records,
            captured_at=workflow.services.clock(context),
        ),
    )
    if current.status != "complete" or current.residual.amount_paise != 0:
        return workflow.stop(
            context, task, "Current settlement sources do not reconcile. Human review required."
        )
    reads = [v for v in task.verifications if v.receipt_id == state.receipt_id]
    if not reads or not max(reads, key=lambda v: v.verified_at).verified:
        return workflow.stop(
            context, task, "Ticket creation is not independently verified. Settlement cannot close."
        )
    credit = fresh[0]
    resolution = SettlementResolution(
        task_id=task.task_id,
        merchant_id=context.merchant_id,
        settlement_reference=proof.settlement_reference,
        baseline_captured_at=proof.captured_at,
        baseline_credit_references=tuple(r.reference for r in baseline),
        outstanding_paise=proof.residual.amount_paise,
        source_reference=credit.reference,
        amount_paise=credit.amount_paise,
        available_at=credit.available_at,
        checked_at=workflow.services.clock(context),
    )
    task = task.with_updates(
        evidence=(*task.evidence, workflow.services._evidence(context, task.task_id, credit)),
        workflow_data={
            **task.workflow_data,
            "settlement_resolution": resolution.model_dump(mode="json"),
        },
    )
    task = with_state(task, state.with_updates(phase="resolved"))
    task = workflow.repo.save(
        context,
        transition_task(
            task,
            S.VERIFYING,
            say("running", task.workflow_data.get("response_language", "en")),
        ),
    )
    return _complete(workflow, context, task)


def _complete(workflow, context, task):
    task = event(
        task,
        "settlement_resolved",
        "Fresh synthetic credit independently resolves the settlement gap.",
    )
    task = task.with_updates(
        next_run_at=None, plan=tuple(p.with_updates(status="done") for p in task.plan)
    )
    return workflow.repo.save(
        context,
        transition_task(
            task,
            S.COMPLETED,
            say("settlement_done", task.workflow_data.get("response_language", "en")),
        ),
    )


def _wait(workflow, context, task, message):
    state = state_of(task)
    if state.follow_up_attempts >= 3:
        return workflow.stop(
            context, task, message + " Follow-up limit reached; human review required."
        )
    task = event(task, "follow_up_waiting", message)
    task = task.with_updates(next_run_at=workflow.services.clock(context) + timedelta(days=1))
    return workflow.repo.save(
        context,
        transition_task(
            task,
            S.WAITING_EXTERNAL,
            say("settlement_wait", task.workflow_data.get("response_language", "en")),
        ),
    )
