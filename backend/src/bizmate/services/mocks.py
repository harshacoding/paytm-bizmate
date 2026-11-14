import hashlib
import json

from pydantic import TypeAdapter

from bizmate.domain.context import MerchantContext, require_context
from bizmate.domain.errors import AccessDenied
from bizmate.domain.models import Evidence, Receipt, Scope
from bizmate.domain.types import Identifier, InputHash, MessageText
from bizmate.persistence.repository import TaskRepository
from bizmate.services.demo import MERCHANTS
from bizmate.services.mock_fixtures import seed_merchant
from bizmate.services.mock_models import (
    CampaignPayload,
    CustomerHistory,
    CustomerRecord,
    FailureControl,
    OrderRecord,
    PaymentRecord,
    SettlementReport,
)
from bizmate.services.mock_store import MockConflictError, SQLiteMockStore


def input_hash(action: str, inputs: dict) -> str:
    content = json.dumps(
        {"action": action, "inputs": inputs}, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(content.encode()).hexdigest()


class MockServices:
    """Synthetic provider adapters. The shared execution engine owns merchant approval."""

    def __init__(self, store: SQLiteMockStore, tasks: TaskRepository, *, controls_enabled=False):
        self.store = store
        self.tasks = tasks
        self.controls_enabled = controls_enabled
        for merchant_id in MERCHANTS:
            seed_merchant(store, merchant_id)

    @staticmethod
    def _scope(context: MerchantContext, scope: Scope):
        require_context(context)
        context.require(scope)

    def _task(self, context: MerchantContext, task_id: str, scope: Scope):
        self._scope(context, scope)
        TypeAdapter(Identifier).validate_python(task_id)
        if self.tasks.get_task(context, task_id) is None:
            raise KeyError("Task not found for the current merchant")

    def _controls(self, context: MerchantContext):
        self._scope(context, Scope.TASKS_WRITE)
        if not self.controls_enabled:
            raise AccessDenied("Demo controls are disabled")

    def clock(self, context: MerchantContext):
        self._scope(context, Scope.TASKS_READ)
        return self.store.clock(context.merchant_id)

    def advance(self, context: MerchantContext, seconds: int):
        self._controls(context)
        return self.store.advance(context.merchant_id, seconds)

    def reset(self, context: MerchantContext):
        self._controls(context)
        seed_merchant(self.store, context.merchant_id, reset=True)
        return self.store.clock(context.merchant_id)

    def inject_failure(self, context: MerchantContext, control: FailureControl):
        self._controls(context)
        control = FailureControl.model_validate(control)
        self.store.inject(context.merchant_id, control.operation, control.count)

    def set_consent(self, context: MerchantContext, customer_id: str, consent: bool):
        self._controls(context)
        context.require(Scope.CUSTOMERS_READ)
        TypeAdapter(Identifier).validate_python(customer_id)
        with self.store.transaction() as connection:
            row = connection.execute(
                """SELECT payload FROM mock_records
                WHERE merchant_id = ? AND kind = 'customer' AND reference = ?""",
                (context.merchant_id, customer_id),
            ).fetchone()
            if row is None:
                raise KeyError("Customer not found")
            customer = CustomerRecord.model_validate_json(row[0]).with_updates(
                marketing_consent=consent
            )
            self.store.put(
                connection,
                context.merchant_id,
                "customer",
                customer_id,
                customer.model_dump(mode="json"),
            )
        return customer

    def _payments(self, context: MerchantContext, operation: str) -> tuple[PaymentRecord, ...]:
        self._scope(context, Scope.PAYMENTS_READ)
        self.store.maybe_fail(context.merchant_id, operation)
        current = self.store.clock(context.merchant_id)
        return tuple(
            record
            for value in self.store.records(context.merchant_id, "payment")
            if (record := PaymentRecord.model_validate(value)).available_at <= current
        )

    def transactions(self, context: MerchantContext) -> tuple[PaymentRecord, ...]:
        return tuple(
            record
            for record in self._payments(context, "get_transactions")
            if record.kind == "sale"
        )

    def deductions(self, context: MerchantContext) -> tuple[PaymentRecord, ...]:
        return tuple(
            record
            for record in self._payments(context, "get_refunds_and_chargebacks")
            if record.kind in {"commission", "gst", "refund", "chargeback"}
        )

    def bank_credits(self, context: MerchantContext) -> tuple[PaymentRecord, ...]:
        return tuple(
            record
            for record in self._payments(context, "get_bank_credits")
            if record.kind == "credit"
        )

    def report(self, context: MerchantContext) -> SettlementReport:
        return SettlementReport(
            records=self._payments(context, "get_settlement_report"),
            captured_at=self.store.clock(context.merchant_id),
        )

    def records(self, context: MerchantContext, task_id: str) -> list[Evidence]:
        self._task(context, task_id, Scope.PAYMENTS_READ)
        return [self._evidence(context, task_id, record) for record in self.report(context).records]

    def ledger_report(self, context: MerchantContext) -> SettlementReport:
        """Fallback to available ledger sources without calling the report service again."""
        credits = tuple(r for r in self._payments(context, "fresh_credits") if r.kind == "credit")
        return SettlementReport(
            records=(*self.transactions(context), *self.deductions(context), *credits),
            captured_at=self.clock(context),
        )

    def follow_up_records(
        self, context: MerchantContext, task_id: str
    ) -> tuple[PaymentRecord, ...]:
        self._task(context, task_id, Scope.PAYMENTS_READ)
        return self._payments(context, "fresh_credits")

    @staticmethod
    def _evidence(context, task_id, record):
        return Evidence(
            task_id=task_id,
            merchant_id=context.merchant_id,
            evidence_id=record.reference,
            source="synthetic_payments",
            source_reference=record.reference,
            description=f"Synthetic {record.kind}",
            amount_paise=record.amount_paise,
            captured_at=record.available_at,
        )

    def fresh_credits(
        self, context: MerchantContext, task_id: str, after_reference: str
    ) -> list[Evidence]:
        self._task(context, task_id, Scope.PAYMENTS_READ)
        records = self._payments(context, "fresh_credits")
        baseline = next(
            (
                record
                for record in records
                if record.reference == after_reference and record.kind == "credit"
            ),
            None,
        )
        if baseline is None:
            raise KeyError("Baseline credit evidence is unavailable")
        return [
            self._evidence(context, task_id, record)
            for record in records
            if record.kind == "credit"
            and record.available_at > baseline.available_at
            and record.settlement_reference == baseline.settlement_reference
        ]

    def customers(self, context: MerchantContext) -> CustomerHistory:
        self._scope(context, Scope.CUSTOMERS_READ)
        self.store.maybe_fail(context.merchant_id, "get_customers_and_orders")
        return CustomerHistory(
            customers=tuple(
                CustomerRecord.model_validate(value)
                for value in self.store.records(context.merchant_id, "customer")
            ),
            orders=tuple(
                OrderRecord.model_validate(value)
                for value in self.store.records(context.merchant_id, "order")
            ),
            evaluated_at=self.store.clock(context.merchant_id),
        )

    def campaign_audience_current(self, context, inputs) -> bool:
        from bizmate.workflows.campaign import segment_inactive_customers

        self._task(context, inputs.task_id, Scope.CUSTOMERS_READ)
        task = self.tasks.get_task(context, inputs.task_id)
        days = task.workflow_data.get("extraction", {}).get("inactivity_days", 30)
        segment = segment_inactive_customers(context, self.customers(context), days)
        return (
            tuple(inputs.recipient_ids) == segment.recipient_ids
            and inputs.cost_paise == segment.estimated_cost_paise
        )

    def prepare_campaign(
        self, context: MerchantContext, task_id: str, payload: CampaignPayload
    ) -> str:
        self._task(context, task_id, Scope.CAMPAIGNS_WRITE)
        context.require(Scope.CUSTOMERS_READ)
        payload = CampaignPayload.model_validate(payload)
        inputs = {"task_id": task_id, **payload.model_dump(mode="json")}
        digest = input_hash("send_campaign", inputs)
        with self.store.transaction() as connection:
            self.store.put(connection, context.merchant_id, "campaign_draft", digest, inputs)
        return digest

    def create(
        self, context: MerchantContext, task_id: str, summary: str, idempotency_key: str
    ) -> Receipt:
        self._task(context, task_id, Scope.TICKETS_WRITE)
        summary = TypeAdapter(MessageText).validate_python(summary)
        return self._write(
            context,
            task_id,
            "create_support_ticket",
            idempotency_key,
            {"task_id": task_id, "summary": summary},
            {"status": "open", "routing": "merchant_support"},
        )

    def send(
        self, context: MerchantContext, task_id: str, approved_input_hash: str, idempotency_key: str
    ) -> Receipt:
        self._task(context, task_id, Scope.CAMPAIGNS_WRITE)
        TypeAdapter(InputHash).validate_python(approved_input_hash)
        drafts = self.store.records(context.merchant_id, "campaign_draft")
        inputs = next(
            (
                draft
                for draft in drafts
                if draft["task_id"] == task_id
                and input_hash("send_campaign", draft) == approved_input_hash
            ),
            None,
        )
        if inputs is None:
            raise KeyError("Matching merchant-owned campaign draft not found")
        count = len(inputs["recipient_ids"])
        failed = min(2, count)
        return self._write(
            context,
            task_id,
            "send_campaign",
            idempotency_key,
            inputs,
            {"delivered": count - failed, "failed": failed},
        )

    def _write(self, context, task_id, action, key, inputs, result) -> Receipt:
        TypeAdapter(Identifier).validate_python(key)
        digest = input_hash(action, inputs)
        current = self.store.clock(context.merchant_id)
        with self.store.transaction() as connection:
            existing = connection.execute(
                """SELECT input_hash, receipt FROM mock_actions
                WHERE merchant_id = ? AND action = ? AND idempotency_key = ?""",
                (context.merchant_id, action, key),
            ).fetchone()
            if existing is not None:
                if existing[0] != digest:
                    raise MockConflictError("Idempotency key is bound to different action inputs")
                return Receipt.model_validate_json(existing[1])
            if action == "send_campaign":
                draft = connection.execute(
                    """SELECT 1 FROM mock_records
                    WHERE merchant_id = ? AND kind = 'campaign_draft' AND reference = ?""",
                    (context.merchant_id, digest),
                ).fetchone()
                if draft is None:
                    raise MockConflictError(
                        "The demo draft was reset. Prepare and review it again."
                    )
                # Recheck eligibility, consent, the complete audience and cost using the
                # same transaction that commits the provider action. Clock/order/consent
                # updates cannot interleave between this check and the write.
                from bizmate.workflows.campaign import segment_inactive_customers

                context.require(Scope.CUSTOMERS_READ)
                task = self.tasks.get_task(context, task_id)
                days = task.workflow_data.get("extraction", {}).get("inactivity_days", 30)
                rows = connection.execute(
                    "SELECT kind, payload FROM mock_records WHERE merchant_id=? "
                    "AND kind IN ('customer','order') ORDER BY reference",
                    (context.merchant_id,),
                ).fetchall()
                clock = connection.execute(
                    "SELECT clock_value FROM mock_clocks WHERE merchant_id=?",
                    (context.merchant_id,),
                ).fetchone()[0]
                history = CustomerHistory(
                    customers=tuple(
                        CustomerRecord.model_validate_json(r["payload"])
                        for r in rows
                        if r["kind"] == "customer"
                    ),
                    orders=tuple(
                        OrderRecord.model_validate_json(r["payload"])
                        for r in rows
                        if r["kind"] == "order"
                    ),
                    evaluated_at=clock,
                )
                segment = segment_inactive_customers(context, history, days)
                if (
                    tuple(inputs["recipient_ids"]) != segment.recipient_ids
                    or inputs["cost_paise"] != segment.estimated_cost_paise
                ):
                    raise MockConflictError("Audience changed. Review and approve a new campaign")
                for customer_id in inputs["recipient_ids"]:
                    row = connection.execute(
                        """SELECT payload FROM mock_records
                        WHERE merchant_id = ? AND kind = 'customer' AND reference = ?""",
                        (context.merchant_id, customer_id),
                    ).fetchone()
                    if (
                        row is None
                        or not CustomerRecord.model_validate_json(row[0]).marketing_consent
                    ):
                        raise MockConflictError(
                            "Recipient consent changed. Review the campaign again."
                        )
            reference = hashlib.sha256(
                f"{context.merchant_id}:{action}:{key}".encode()
            ).hexdigest()[:24]
            receipt = Receipt(
                task_id=task_id,
                merchant_id=context.merchant_id,
                receipt_id=f"receipt-{reference}",
                external_reference=f"mock-{reference}",
                action=action,
                idempotency_key=key,
                input_hash=digest,
                created_at=current,
            )
            connection.execute(
                """INSERT INTO mock_actions (reference, merchant_id, action, task_id,
                   idempotency_key, input_hash, receipt, result, inputs)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    receipt.external_reference,
                    context.merchant_id,
                    action,
                    task_id,
                    key,
                    digest,
                    receipt.model_dump_json(),
                    json.dumps(result),
                    json.dumps(inputs),
                ),
            )
        self.store.maybe_fail(
            context.merchant_id,
            "campaign_after_write" if action == "send_campaign" else "ticket_after_write",
        )
        return receipt

    def lookup(self, context: MerchantContext, action: str, idempotency_key: str) -> Receipt | None:
        scope = {
            "create_support_ticket": Scope.TICKETS_WRITE,
            "send_campaign": Scope.CAMPAIGNS_WRITE,
        }[action]
        self._scope(context, scope)
        return self.store.find(context.merchant_id, action, idempotency_key)

    def status(self, context: MerchantContext, reference: str) -> str:
        self._scope(context, Scope.TICKETS_WRITE)
        self.store.maybe_fail(context.merchant_id, "get_ticket_status")
        return json.loads(
            self.store.action(context.merchant_id, "create_support_ticket", reference)["result"]
        )["status"]

    def delivery(self, context: MerchantContext, reference: str) -> dict[str, int]:
        self._scope(context, Scope.CAMPAIGNS_WRITE)
        self.store.maybe_fail(context.merchant_id, "get_campaign_delivery_status")
        return json.loads(
            self.store.action(context.merchant_id, "send_campaign", reference)["result"]
        )
