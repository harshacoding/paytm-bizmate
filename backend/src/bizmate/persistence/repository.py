from threading import RLock
from typing import Protocol

from bizmate.domain.context import MerchantContext, require_context
from bizmate.domain.lifecycle import require_transition
from bizmate.domain.models import Scope, Task


class TaskRepository(Protocol):
    """BM-03: SQLite adapter must preserve merchant scoping and detached snapshots."""

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
                key=lambda t: t.created_at,
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
        # Revalidate even internal model_copy/model_construct input before storage.
        task = Task.model_validate(task.model_dump())
        with self._lock:
            existing = self._tasks.get(task.task_id)
            if existing:
                context.require_owner(existing.merchant_id)
                if task.status != existing.status:
                    require_transition(existing.status, task.status)
                if task.created_at != existing.created_at or task.updated_at < existing.updated_at:
                    raise ValueError("Task creation time is immutable; updates cannot go backwards")
            self._tasks[task.task_id] = task.model_copy(deep=True)
            return task.model_copy(deep=True)
