import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bizmate.domain.models import Receipt

DEMO_START = datetime(2026, 11, 14, 4, tzinfo=UTC)


class MockConflictError(ValueError):
    pass


class MockTimeout(TimeoutError):
    """Persisted failure script. A write may already have committed when this is raised."""


class SQLiteMockStore:
    def __init__(self, database_path: str | Path):
        self.path = Path(database_path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS mock_clocks (
                merchant_id TEXT PRIMARY KEY, clock_value TEXT NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS mock_records (
                merchant_id TEXT NOT NULL, kind TEXT NOT NULL, reference TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY (merchant_id, kind, reference))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS mock_actions (
                reference TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, action TEXT NOT NULL,
                task_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, input_hash TEXT NOT NULL,
                receipt TEXT NOT NULL, result TEXT NOT NULL, inputs TEXT NOT NULL,
                UNIQUE (merchant_id, action, idempotency_key))""")
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(mock_actions)")}
            if "inputs" not in columns:
                connection.execute(
                    "ALTER TABLE mock_actions ADD COLUMN inputs TEXT NOT NULL DEFAULT '{}'"
                )
            connection.execute("""CREATE TABLE IF NOT EXISTS mock_failures (
                merchant_id TEXT NOT NULL, operation TEXT NOT NULL, remaining INTEGER NOT NULL,
                PRIMARY KEY (merchant_id, operation))""")

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.path, timeout=5)) as connection, connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            yield connection

    @staticmethod
    def put(connection, merchant_id: str, kind: str, reference: str, payload: dict):
        connection.execute(
            """INSERT INTO mock_records VALUES (?, ?, ?, ?)
            ON CONFLICT(merchant_id, kind, reference) DO UPDATE SET payload = excluded.payload""",
            (merchant_id, kind, reference, json.dumps(payload)),
        )

    def records(self, merchant_id: str, kind: str) -> list[dict]:
        with self.transaction() as connection:
            rows = connection.execute(
                """SELECT payload FROM mock_records WHERE merchant_id = ? AND kind = ?
                   ORDER BY reference""",
                (merchant_id, kind),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def clock(self, merchant_id: str) -> datetime:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT clock_value FROM mock_clocks WHERE merchant_id = ?", (merchant_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Demo merchant has not been seeded")
        return datetime.fromisoformat(row[0])

    def advance(self, merchant_id: str, seconds: int) -> datetime:
        if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0:
            raise ValueError("Clock advancement must be a positive integer number of seconds")
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT clock_value FROM mock_clocks WHERE merchant_id = ?", (merchant_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Demo merchant has not been seeded")
            try:
                current = datetime.fromisoformat(row[0]) + timedelta(seconds=seconds)
            except OverflowError as exc:
                raise ValueError("Clock advancement exceeds the supported date range") from exc
            connection.execute(
                "UPDATE mock_clocks SET clock_value = ? WHERE merchant_id = ?",
                (current.isoformat(), merchant_id),
            )
        return current

    def inject(self, merchant_id: str, operation: str, count: int):
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO mock_failures VALUES (?, ?, ?)
                ON CONFLICT(merchant_id, operation) DO UPDATE SET remaining = excluded.remaining""",
                (merchant_id, operation, count),
            )

    def maybe_fail(self, merchant_id: str, operation: str):
        with self.transaction() as connection:
            cursor = connection.execute(
                """UPDATE mock_failures SET remaining = remaining - 1
                WHERE merchant_id = ? AND operation = ? AND remaining > 0""",
                (merchant_id, operation),
            )
            failed = cursor.rowcount == 1
        if failed:
            raise MockTimeout(f"Synthetic timeout during {operation}")

    def action(self, merchant_id: str, action: str, reference: str) -> dict:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM mock_actions
                WHERE merchant_id = ? AND action = ? AND reference = ?""",
                (merchant_id, action, reference),
            ).fetchone()
        if row is None:
            raise KeyError("Mock action not found")
        return dict(row)

    def find(self, merchant_id: str, action: str, key: str) -> Receipt | None:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT receipt FROM mock_actions
                WHERE merchant_id = ? AND action = ? AND idempotency_key = ?""",
                (merchant_id, action, key),
            ).fetchone()
        return Receipt.model_validate_json(row[0]) if row else None
