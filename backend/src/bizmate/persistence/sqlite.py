import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import UTC
from pathlib import Path

from bizmate.domain.context import MerchantContext, require_context
from bizmate.domain.models import Scope, Task
from bizmate.persistence.repository import task_snapshot


def load_task(payload: str) -> Task:
    data = json.loads(payload)
    legacy_executions = data.pop("executions", None)
    if legacy_executions is not None:
        data.setdefault("tool_executions", legacy_executions)
        legacy_hashes = {}
        for field in [
            "plan",
            "evidence",
            "approvals",
            "receipts",
            "verifications",
            "tool_executions",
        ]:
            for record in data.get(field, []):
                record.setdefault("task_id", data["task_id"])
                record.setdefault("merchant_id", data["merchant_id"])
                digest = record.get("input_hash")
                if digest is not None and not re.fullmatch(r"[0-9a-f]{64}", digest):
                    legacy_hashes[digest] = hashlib.sha256(digest.encode()).hexdigest()
                    record["input_hash"] = legacy_hashes[digest]
        for execution in data["tool_executions"]:
            execution["outcome"] = {"error": "failed", "success": "succeeded"}.get(
                execution["outcome"], execution["outcome"]
            )
        for receipt in data.get("receipts", []):
            approval = next(
                (
                    item
                    for item in data.get("approvals", [])
                    if item["input_hash"] == receipt["input_hash"]
                ),
                None,
            )
            receipt.setdefault("action", approval["action"] if approval else "legacy_action")
            receipt.setdefault("idempotency_key", receipt["receipt_id"])
        if legacy_hashes:
            data.setdefault("workflow_data", {})["legacy_input_hashes"] = legacy_hashes
    return Task.model_validate(data)


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
                if version > 2:
                    raise RuntimeError("Database schema is newer than this backend supports")
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        merchant_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK (revision > 0),
                        payload TEXT NOT NULL,
                        conversation_id TEXT
                    )"""
                )
                connection.execute(
                    """CREATE INDEX IF NOT EXISTS tasks_merchant_created
                       ON tasks (merchant_id, created_at DESC, task_id DESC)"""
                )
                columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
                if "conversation_id" not in columns:
                    connection.execute("ALTER TABLE tasks ADD COLUMN conversation_id TEXT")
                    for task_id, payload in connection.execute(
                        "SELECT task_id, payload FROM tasks"
                    ):
                        conversation_id = json.loads(payload).get("conversation_id")
                        connection.execute(
                            "UPDATE tasks SET conversation_id = ? WHERE task_id = ?",
                            (conversation_id, task_id),
                        )
                connection.execute(
                    """CREATE INDEX IF NOT EXISTS tasks_merchant_conversation
                       ON tasks (merchant_id, conversation_id)"""
                )
                connection.execute("PRAGMA user_version = 2")

    def _connect(self) -> sqlite3.Connection:
        # Connections belong to one operation, so FastAPI workers never share a connection.
        return sqlite3.connect(self.database_path, timeout=5)

    def list_tasks(self, context: MerchantContext) -> list[Task]:
        require_context(context)
        context.require(Scope.TASKS_READ)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT payload FROM tasks WHERE merchant_id = ?
                   ORDER BY created_at DESC, task_id DESC""",
                (context.merchant_id,),
            ).fetchall()
        return [load_task(row[0]) for row in rows]

    def get_task(self, context: MerchantContext, task_id: str) -> Task | None:
        require_context(context)
        context.require(Scope.TASKS_READ)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM tasks WHERE merchant_id = ? AND task_id = ?",
                (context.merchant_id, task_id),
            ).fetchone()
        return load_task(row[0]) if row else None

    def save(self, context: MerchantContext, task: Task) -> Task:
        require_context(context)
        context.require(Scope.TASKS_WRITE)
        context.require_owner(task.merchant_id)
        with closing(self._connect()) as connection, connection:
            # Acquire the write lock before checking ownership and the expected revision.
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT merchant_id, payload FROM tasks WHERE task_id = ?",
                (task.task_id,),
            ).fetchone()
            if existing:
                context.require_owner(existing[0])
            snapshot = task_snapshot(context, task, load_task(existing[1]) if existing else None)
            connection.execute(
                """INSERT INTO tasks
                   (task_id, merchant_id, created_at, revision, payload, conversation_id)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                       created_at = excluded.created_at,
                       revision = excluded.revision,
                       conversation_id = excluded.conversation_id,
                       payload = excluded.payload""",
                (
                    snapshot.task_id,
                    snapshot.merchant_id,
                    snapshot.created_at.astimezone(UTC).isoformat(),
                    snapshot.revision,
                    snapshot.model_dump_json(),
                    snapshot.conversation_id,
                ),
            )
        return snapshot
