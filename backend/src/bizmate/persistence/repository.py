from datetime import UTC
from threading import Lock
from typing import Protocol

from bizmate.domain.models import Task, now


class TaskConflictError(Exception):
    """A saved task has changed since the caller read it."""


def task_snapshot(task: Task) -> Task:
    snapshot = Task.model_validate(task.model_dump())
    snapshot.events.sort(
        key=lambda event: event.occurred_at.replace(tzinfo=event.occurred_at.tzinfo or UTC)
    )
    return snapshot


class TaskRepository(Protocol):
    """Merchant-scoped snapshots. Save returns the next revision or raises a conflict."""

    def list_tasks(self, merchant_id: str) -> list[Task]: ...
    def get_task(self, merchant_id: str, task_id: str) -> Task | None: ...
    def save(self, task: Task) -> Task: ...


class MemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = Lock()

    def list_tasks(self, merchant_id: str) -> list[Task]:
        with self._lock:
            return sorted(
                [
                    t.model_copy(deep=True)
                    for t in self._tasks.values()
                    if t.merchant_id == merchant_id
                ],
                key=lambda t: (t.created_at.replace(tzinfo=t.created_at.tzinfo or UTC), t.task_id),
                reverse=True,
            )

    def get_task(self, merchant_id: str, task_id: str) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.merchant_id != merchant_id:
                return None
            return task.model_copy(deep=True)

    def save(self, task: Task) -> Task:
        snapshot = task_snapshot(task)
        with self._lock:
            existing = self._tasks.get(snapshot.task_id)
            if existing and existing.merchant_id != snapshot.merchant_id:
                raise ValueError("Task ownership cannot change")
            revision = existing.revision if existing else 0
            if snapshot.revision != revision:
                raise TaskConflictError("Task changed. Reload it before saving.")
            snapshot.revision += 1
            snapshot.updated_at = now()
            self._tasks[snapshot.task_id] = snapshot
            return snapshot.model_copy(deep=True)
