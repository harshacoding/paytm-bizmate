from threading import RLock
from typing import Protocol

from bizmate.domain.context import MerchantContext, require_context
from bizmate.domain.lifecycle import require_transition
from bizmate.domain.models import Scope, Task, now


class TaskConflictError(Exception):
    """The saved task changed after the caller read its snapshot."""


def task_snapshot(context: MerchantContext, task: Task, existing: Task | None) -> Task:
    require_context(context)
    context.require(Scope.TASKS_WRITE)
    context.require_owner(task.merchant_id)
    task = Task.model_validate(task.model_dump(warnings=False))
    if existing is not None:
        context.require_owner(existing.merchant_id)
    revision = existing.revision if existing is not None else 0
    if task.revision != revision:
        raise TaskConflictError("Task changed. Reload it before saving.")
    if existing is not None:
        if task.created_at != existing.created_at or task.updated_at < existing.updated_at:
            raise ValueError("Task creation time is immutable; updates cannot go backwards")
        if task.status != existing.status:
            require_transition(existing.status, task.status)
    return task.with_updates(
        revision=revision + 1,
        updated_at=max(now(), task.updated_at),
        events=tuple(sorted(task.events, key=lambda event: event.occurred_at)),
    )


class TaskRepository(Protocol):
    """Context-scoped snapshots. Save returns the next revision or raises a conflict."""

    def list_tasks(self, context: MerchantContext) -> list[Task]: ...
    def get_task(self, context: MerchantContext, task_id: str) -> Task | None: ...
    def save(self, context: MerchantContext, task: Task) -> Task: ...


class MemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = RLock()

    def list_tasks(self, context: MerchantContext) -> list[Task]:
        require_context(context)
        context.require(Scope.TASKS_READ)
        with self._lock:
            return sorted(
                [
                    t.model_copy(deep=True)
                    for t in self._tasks.values()
                    if t.merchant_id == context.merchant_id
                ],
                key=lambda t: (t.created_at, t.task_id),
                reverse=True,
            )

    def get_task(self, context: MerchantContext, task_id: str) -> Task | None:
        require_context(context)
        context.require(Scope.TASKS_READ)
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.merchant_id != context.merchant_id:
                return None
            return task.model_copy(deep=True)

    def save(self, context: MerchantContext, task: Task) -> Task:
        require_context(context)
        context.require(Scope.TASKS_WRITE)
        context.require_owner(task.merchant_id)
        with self._lock:
            existing = self._tasks.get(task.task_id)
            snapshot = task_snapshot(context, task, existing)
            self._tasks[task.task_id] = snapshot
            return snapshot.model_copy(deep=True)
