from typing import Protocol

from bizmate.domain.models import Task


class TaskRepository(Protocol):
    """BM-03: SQLite adapter must preserve merchant scoping and detached snapshots."""

    def list_tasks(self, merchant_id: str) -> list[Task]: ...
    def get_task(self, merchant_id: str, task_id: str) -> Task | None: ...
    def save(self, task: Task) -> Task: ...


class MemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def list_tasks(self, merchant_id: str) -> list[Task]:
        return sorted(
            [t.model_copy(deep=True) for t in self._tasks.values() if t.merchant_id == merchant_id],
            key=lambda t: t.created_at,
            reverse=True,
        )

    def get_task(self, merchant_id: str, task_id: str) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None or task.merchant_id != merchant_id:
            return None
        return task.model_copy(deep=True)

    def save(self, task: Task) -> Task:
        existing = self._tasks.get(task.task_id)
        if existing and existing.merchant_id != task.merchant_id:
            raise ValueError("Task ownership cannot change")
        self._tasks[task.task_id] = task.model_copy(deep=True)
        return task.model_copy(deep=True)
