"""Domain transition rules; workflow-specific outcome semantics remain in BM-06/07/11."""

from datetime import datetime
from types import MappingProxyType

from bizmate.domain.models import Task, TaskEvent, TaskStatus, now

S = TaskStatus
TRANSITIONS = MappingProxyType(
    {
        S.CREATED: frozenset({S.PLANNING, S.ESCALATED, S.FAILED}),
        S.PLANNING: frozenset({S.READY, S.AWAITING_INPUT, S.ESCALATED, S.FAILED}),
        S.READY: frozenset(
            {S.RUNNING, S.AWAITING_INPUT, S.AWAITING_APPROVAL, S.ESCALATED, S.FAILED}
        ),
        S.RUNNING: frozenset(
            {
                S.PLANNING,
                S.AWAITING_INPUT,
                S.AWAITING_APPROVAL,
                S.WAITING_EXTERNAL,
                S.VERIFYING,
                S.ESCALATED,
                S.FAILED,
            }
        ),
        S.AWAITING_INPUT: frozenset({S.PLANNING, S.ESCALATED, S.FAILED}),
        S.AWAITING_APPROVAL: frozenset({S.READY, S.PLANNING, S.ESCALATED, S.FAILED}),
        S.WAITING_EXTERNAL: frozenset(
            {S.RUNNING, S.VERIFYING, S.AWAITING_INPUT, S.ESCALATED, S.FAILED}
        ),
        S.VERIFYING: frozenset(
            {S.COMPLETED, S.WAITING_EXTERNAL, S.PLANNING, S.ESCALATED, S.FAILED}
        ),
        S.COMPLETED: frozenset(),
        S.ESCALATED: frozenset(),
        S.FAILED: frozenset(),
    }
)


def require_transition(source: TaskStatus, target: TaskStatus) -> None:
    if target not in TRANSITIONS[source]:
        raise ValueError(f"Invalid task transition: {source} -> {target}")


def transition_task(
    task: Task, target: TaskStatus, next_action: str, *, occurred_at: datetime | None = None
) -> Task:
    require_transition(task.status, target)
    timestamp = occurred_at or now()
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Transition timestamp must include a timezone")
    if timestamp < task.updated_at:
        raise ValueError("Transition timestamp cannot precede the last task update")
    return task.with_updates(
        status=target,
        next_action=next_action,
        updated_at=timestamp,
        events=(
            *task.events,
            TaskEvent(
                kind="status_changed", occurred_at=timestamp, message=f"{task.status} -> {target}"
            ),
        ),
    )
