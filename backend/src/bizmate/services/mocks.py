import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bizmate.domain.models import CapabilityGap, Evidence, Receipt
from bizmate.services.models import (
    CampaignInputs,
    Credit,
    Customer,
    Order,
    SettlementRecords,
    TicketInputs,
)

DEMO_START = datetime(2026, 11, 14, 9, tzinfo=UTC)


def action_hash(action: str, inputs: dict) -> str:
    payload = json.dumps(
        {"action": action, "inputs": inputs}, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class MockTimeout(TimeoutError):
    """Scripted synthetic service failure, including an uncertain committed write."""


class MockServices:
    """Merchant-scoped, stateful synthetic providers in the local SQLite database."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS demo_clocks (
                    merchant_id TEXT PRIMARY KEY, current_time TEXT NOT NULL)"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS mock_records (
                    merchant_id TEXT NOT NULL, kind TEXT NOT NULL, reference TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY (merchant_id, kind, reference))"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS mock_actions (
                    reference TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, kind TEXT NOT NULL,
                    task_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, input_hash TEXT NOT NULL,
                    inputs TEXT NOT NULL, receipt TEXT NOT NULL, result TEXT NOT NULL,
                    UNIQUE (merchant_id, kind, idempotency_key))"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS mock_failures (
                    merchant_id TEXT NOT NULL, operation TEXT NOT NULL, remaining INTEGER NOT NULL,
                    PRIMARY KEY (merchant_id, operation))"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS capability_gaps (
                    gap_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, payload TEXT NOT NULL)"""
            )
            for merchant_id in ["merchant_demo", "merchant_other"]:
                self._seed(connection, merchant_id)

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.database_path, timeout=5)) as connection, connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            yield connection

    def _record(self, connection, merchant_id: str, kind: str, reference: str, payload: dict):
        connection.execute(
            "INSERT INTO mock_records VALUES (?, ?, ?, ?)",
            (merchant_id, kind, reference, json.dumps(payload)),
        )

    def _seed(self, connection, merchant_id: str):
        exists = connection.execute(
            "SELECT 1 FROM demo_clocks WHERE merchant_id = ?", (merchant_id,)
        ).fetchone()
        if exists:
            return
        connection.execute(
            "INSERT INTO demo_clocks VALUES (?, ?)", (merchant_id, DEMO_START.isoformat())
        )
        for index in range(200):
            customer_id = f"customer-{index + 1:03}"
            self._record(
                connection,
                merchant_id,
                "customer",
                customer_id,
                {
                    "customer_id": customer_id,
                    "marketing_consent": index < 180,
                },
            )
            days = 30 + index % 31 if index < 120 else 10
            self._record(
                connection,
                merchant_id,
                "order",
                f"order-{index + 1:03}",
                {
                    "order_id": f"order-{index + 1:03}",
                    "customer_id": customer_id,
                    "ordered_at": (DEMO_START - timedelta(days=days)).isoformat(),
                    "qualifying": True,
                },
            )
        settlement = SettlementRecords(
            settlement_reference="settlement-001",
            sales_paise=2000000,
            commission_paise=24000,
            gst_paise=4320,
            refunds_paise=80000,
            chargeback_paise=35000,
            bank_credit_paise=1840000,
            bank_credit_reference="credit-001",
        )
        self._record(
            connection,
            merchant_id,
            "settlement",
            "settlement-001",
            settlement.model_dump(mode="json"),
        )
        for reference, amount, delay in [("credit-001", 1840000, 0), ("credit-held-001", 16680, 1)]:
            credit = Credit(
                reference=reference,
                settlement_reference="settlement-001",
                amount_paise=amount,
                available_at=DEMO_START + timedelta(days=delay),
            )
            self._record(
                connection, merchant_id, "credit", reference, credit.model_dump(mode="json")
            )

    def clock(self, merchant_id: str) -> datetime:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT current_time FROM demo_clocks WHERE merchant_id = ?", (merchant_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Unknown demo merchant")
        return datetime.fromisoformat(row[0])

    def advance(self, merchant_id: str, seconds: int) -> datetime:
        if seconds <= 0:
            raise ValueError("Time advancement must be positive")
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT current_time FROM demo_clocks WHERE merchant_id = ?", (merchant_id,)
            ).fetchone()
            current = datetime.fromisoformat(row[0]) + timedelta(seconds=seconds)
            connection.execute(
                "UPDATE demo_clocks SET current_time = ? WHERE merchant_id = ?",
                (current.isoformat(), merchant_id),
            )
        return current

    def records_of(self, merchant_id: str, kind: str) -> list[dict]:
        with self.transaction() as connection:
            rows = connection.execute(
                """SELECT payload FROM mock_records WHERE merchant_id = ? AND kind = ?
                   ORDER BY reference""",
                (merchant_id, kind),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def customers_and_orders(self, merchant_id: str) -> tuple[list[Customer], list[Order]]:
        return (
            [Customer.model_validate(item) for item in self.records_of(merchant_id, "customer")],
            [Order.model_validate(item) for item in self.records_of(merchant_id, "order")],
        )

    def set_consent(self, merchant_id: str, customer_id: str, consent: bool):
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT payload FROM mock_records
                   WHERE merchant_id = ? AND kind = 'customer' AND reference = ?""",
                (merchant_id, customer_id),
            ).fetchone()
            if row is None:
                raise KeyError("Customer not found")
            customer = Customer.model_validate_json(row[0])
            customer.marketing_consent = consent
            connection.execute(
                """UPDATE mock_records SET payload = ?
                   WHERE merchant_id = ? AND kind = 'customer' AND reference = ?""",
                (customer.model_dump_json(), merchant_id, customer_id),
            )

    def inject_failure(self, merchant_id: str, operation: str, count: int):
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO mock_failures VALUES (?, ?, ?) ON CONFLICT(merchant_id, operation)
                   DO UPDATE SET remaining = excluded.remaining""",
                (merchant_id, operation, count),
            )

    def _fail(self, merchant_id: str, operation: str):
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT remaining FROM mock_failures WHERE merchant_id = ? AND operation = ?",
                (merchant_id, operation),
            ).fetchone()
            should_fail = row is not None and row[0] > 0
            if should_fail:
                connection.execute(
                    """UPDATE mock_failures SET remaining = remaining - 1
                       WHERE merchant_id = ? AND operation = ?""",
                    (merchant_id, operation),
                )
        if should_fail:
            raise MockTimeout(f"Synthetic timeout during {operation}")

    def settlement(self, merchant_id: str, *, fallback: bool = False) -> SettlementRecords:
        if not fallback:
            self._fail(merchant_id, "settlement_report")
        records = self.records_of(merchant_id, "settlement")
        if len(records) != 1:
            raise ValueError("Settlement evidence is incomplete or conflicting")
        return SettlementRecords.model_validate(records[0])

    def records(self, merchant_id: str) -> list[Evidence]:
        record = self.settlement(merchant_id)
        return [
            Evidence(
                evidence_id=f"{record.settlement_reference}-{field}",
                source="mock_settlement",
                source_reference=record.settlement_reference,
                description=field,
                amount_paise=value,
                captured_at=self.clock(merchant_id),
            )
            for field, value in record.model_dump().items()
            if field.endswith("_paise")
        ]

    def fresh_credits(self, merchant_id: str, after_reference: str) -> list[Credit]:
        self._fail(merchant_id, "fresh_credits")
        credits = [Credit.model_validate(item) for item in self.records_of(merchant_id, "credit")]
        baseline = next((credit for credit in credits if credit.reference == after_reference), None)
        if baseline is None:
            raise ValueError("Baseline credit evidence is missing")
        current = self.clock(merchant_id)
        return [
            credit
            for credit in credits
            if baseline.available_at < credit.available_at <= current
            and credit.settlement_reference == baseline.settlement_reference
        ]

    def find_action(self, merchant_id: str, kind: str, idempotency_key: str) -> Receipt | None:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT receipt FROM mock_actions
                   WHERE merchant_id = ? AND kind = ? AND idempotency_key = ?""",
                (merchant_id, kind, idempotency_key),
            ).fetchone()
        return Receipt.model_validate_json(row[0]) if row else None

    def _write(
        self, merchant_id: str, kind: str, inputs: dict, idempotency_key: str, result: dict
    ) -> Receipt:
        digest = action_hash(kind, inputs)
        current = self.clock(merchant_id)
        with self.transaction() as connection:
            existing = connection.execute(
                """SELECT input_hash, receipt FROM mock_actions
                   WHERE merchant_id = ? AND kind = ? AND idempotency_key = ?""",
                (merchant_id, kind, idempotency_key),
            ).fetchone()
            if existing:
                if existing[0] != digest:
                    raise ValueError("Idempotency key is already bound to different inputs")
                return Receipt.model_validate_json(existing[1])
            if kind == "send_campaign":
                recipients = inputs["recipient_ids"]
                if (
                    len(set(recipients)) != len(recipients)
                    or inputs["cost_paise"] != len(recipients) * 200
                ):
                    raise ValueError("Campaign audience or cost is invalid")
                for customer_id in recipients:
                    row = connection.execute(
                        """SELECT payload FROM mock_records
                           WHERE merchant_id = ? AND kind = 'customer' AND reference = ?""",
                        (merchant_id, customer_id),
                    ).fetchone()
                    if row is None or not Customer.model_validate_json(row[0]).marketing_consent:
                        raise ValueError("Campaign consent changed. Review the audience again.")
            reference_digest = hashlib.sha256(
                f"{merchant_id}:{idempotency_key}".encode()
            ).hexdigest()
            reference = f"{kind}-{reference_digest[:20]}"
            receipt = Receipt(
                receipt_id=f"receipt-{reference}",
                task_id=inputs["task_id"],
                external_reference=reference,
                input_hash=digest,
                created_at=current,
            )
            connection.execute(
                "INSERT INTO mock_actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    reference,
                    merchant_id,
                    kind,
                    inputs["task_id"],
                    idempotency_key,
                    digest,
                    json.dumps(inputs),
                    receipt.model_dump_json(),
                    json.dumps(result),
                ),
            )
        self._fail(
            merchant_id, "campaign_after_write" if kind == "send_campaign" else "ticket_after_write"
        )
        return receipt

    def create(self, merchant_id: str, inputs: TicketInputs, idempotency_key: str) -> Receipt:
        return self._write(
            merchant_id,
            "create_support_ticket",
            inputs.model_dump(),
            idempotency_key,
            {"status": "open"},
        )

    def send(self, merchant_id: str, inputs: CampaignInputs, idempotency_key: str) -> Receipt:
        count = len(inputs.recipient_ids)
        failed = min(2, count)
        return self._write(
            merchant_id,
            "send_campaign",
            inputs.model_dump(),
            idempotency_key,
            {"delivered": count - failed, "failed": failed},
        )

    def _read_action(self, merchant_id: str, kind: str, reference: str) -> dict:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT result FROM mock_actions
                   WHERE merchant_id = ? AND kind = ? AND reference = ?""",
                (merchant_id, kind, reference),
            ).fetchone()
        if row is None:
            raise KeyError("Mock action not found")
        return json.loads(row[0])

    def status(self, merchant_id: str, reference: str) -> str:
        self._fail(merchant_id, "ticket_status")
        return self._read_action(merchant_id, "create_support_ticket", reference)["status"]

    def delivery(self, merchant_id: str, reference: str) -> dict[str, int]:
        self._fail(merchant_id, "campaign_delivery")
        return self._read_action(merchant_id, "send_campaign", reference)

    def record_gap(self, gap: CapabilityGap):
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO capability_gaps VALUES (?, ?, ?) ON CONFLICT(gap_id)
                   DO UPDATE SET payload = excluded.payload""",
                (gap.gap_id, gap.merchant_id, gap.model_dump_json()),
            )

    def reset(self, merchant_id: str):
        with self.transaction() as connection:
            for table in [
                "mock_records",
                "mock_actions",
                "mock_failures",
                "capability_gaps",
                "demo_clocks",
                "tasks",
            ]:
                connection.execute(f"DELETE FROM {table} WHERE merchant_id = ?", (merchant_id,))
            self._seed(connection, merchant_id)
