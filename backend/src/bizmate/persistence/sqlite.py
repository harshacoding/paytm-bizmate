import sqlite3
from contextlib import closing
from datetime import UTC
from pathlib import Path

from bizmate.domain.models import Task, now
from bizmate.persistence.repository import TaskConflictError, task_snapshot


class SQLiteTaskRepository:
    """Durable task snapshots with atomic writes and optimistic concurrency control."""

    def __init__(self, database_path: str | Path) -> None:
        if str(database_path) == ":memory:":
            raise ValueError("SQLiteTaskRepository requires a filesystem database path")
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > 1:
                    raise RuntimeError("Database schema is newer than this backend supports")
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        merchant_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK (revision > 0),
                        payload TEXT NOT NULL
                    )"""
                )
                connection.execute(
                    """CREATE INDEX IF NOT EXISTS tasks_merchant_created
                       ON tasks (merchant_id, created_at DESC, task_id DESC)"""
                )
                connection.execute("PRAGMA user_version = 1")

    def _connect(self) -> sqlite3.Connection:
        # Connections belong to one operation, so FastAPI workers never share a connection.
        return sqlite3.connect(self.database_path, timeout=5)

    def list_tasks(self, merchant_id: str) -> list[Task]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT payload FROM tasks WHERE merchant_id = ?
                   ORDER BY created_at DESC, task_id DESC""",
                (merchant_id,),
            ).fetchall()
        return [Task.model_validate_json(row[0]) for row in rows]

    def get_task(self, merchant_id: str, task_id: str) -> Task | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM tasks WHERE merchant_id = ? AND task_id = ?",
                (merchant_id, task_id),
            ).fetchone()
        return Task.model_validate_json(row[0]) if row else None

    def save(self, task: Task) -> Task:
        snapshot = task_snapshot(task)
        with closing(self._connect()) as connection, connection:
            # Acquire the write lock before checking ownership and the expected revision.
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT merchant_id, revision FROM tasks WHERE task_id = ?",
                (snapshot.task_id,),
            ).fetchone()
            if existing and existing[0] != snapshot.merchant_id:
                raise ValueError("Task ownership cannot change")
            revision = existing[1] if existing else 0
            if snapshot.revision != revision:
                raise TaskConflictError("Task changed. Reload it before saving.")
            snapshot.revision += 1
            snapshot.updated_at = now()
            created_at = snapshot.created_at.replace(tzinfo=snapshot.created_at.tzinfo or UTC)
            connection.execute(
                """INSERT INTO tasks (task_id, merchant_id, created_at, revision, payload)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                       created_at = excluded.created_at,
                       revision = excluded.revision,
                       payload = excluded.payload""",
                (
                    snapshot.task_id,
                    snapshot.merchant_id,
                    created_at.astimezone(UTC).isoformat(),
                    snapshot.revision,
                    snapshot.model_dump_json(),
                ),
            )
        return snapshot
