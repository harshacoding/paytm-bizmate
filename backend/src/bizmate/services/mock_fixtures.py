from datetime import timedelta

from bizmate.services.mock_models import CustomerRecord, OrderRecord, PaymentRecord
from bizmate.services.mock_store import DEMO_START, SQLiteMockStore


def seed_merchant(store: SQLiteMockStore, merchant_id: str, *, reset: bool = False):
    with store.transaction() as connection:
        existing = connection.execute(
            "SELECT 1 FROM mock_clocks WHERE merchant_id = ?", (merchant_id,)
        ).fetchone()
        if existing and not reset:
            return
        if reset:
            for table in ["mock_records", "mock_actions", "mock_failures", "mock_clocks"]:
                connection.execute(f"DELETE FROM {table} WHERE merchant_id = ?", (merchant_id,))
        connection.execute(
            "INSERT INTO mock_clocks VALUES (?, ?)", (merchant_id, DEMO_START.isoformat())
        )
        for index in range(200):
            record = PaymentRecord(
                reference=f"txn-{index + 1:03}",
                kind="sale",
                amount_paise=10000,
                available_at=DEMO_START,
            )
            store.put(
                connection, merchant_id, "payment", record.reference, record.model_dump(mode="json")
            )
            customer_id = f"customer-{index + 1:03}"
            customer = CustomerRecord(customer_id=customer_id, marketing_consent=index < 180)
            days = 30 + index % 31 if index < 120 else 10
            order = OrderRecord(
                order_id=f"order-{index + 1:03}",
                customer_id=customer_id,
                ordered_at=DEMO_START - timedelta(days=days),
            )
            store.put(
                connection, merchant_id, "customer", customer_id, customer.model_dump(mode="json")
            )
            store.put(
                connection, merchant_id, "order", order.order_id, order.model_dump(mode="json")
            )
        for kind, amount in [
            ("commission", 24000),
            ("gst", 4320),
            ("refund", 80000),
            ("chargeback", 35000),
        ]:
            record = PaymentRecord(
                reference=f"{kind}-001", kind=kind, amount_paise=amount, available_at=DEMO_START
            )
            store.put(
                connection, merchant_id, "payment", record.reference, record.model_dump(mode="json")
            )
        for reference, amount, delay in [("credit-001", 1840000, 0), ("credit-held-001", 16680, 1)]:
            record = PaymentRecord(
                reference=reference,
                kind="credit",
                amount_paise=amount,
                available_at=DEMO_START + timedelta(days=delay),
            )
            store.put(connection, merchant_id, "payment", reference, record.model_dump(mode="json"))
