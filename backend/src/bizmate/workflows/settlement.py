from bizmate.domain.errors import FeaturePending
from bizmate.services.models import SettlementRecords


def reconcile_settlement(records: SettlementRecords | None = None) -> dict:
    """Integer-paise service boundary for follow-up; BM-11 owns conversational investigation."""
    if records is None:
        raise FeaturePending("BM-10", "Settlement records are required for reconciliation.")
    expected = (
        records.sales_paise
        - records.commission_paise
        - records.gst_paise
        - records.refunds_paise
        - records.chargeback_paise
    )
    if expected < 0:
        raise ValueError("Settlement deductions exceed the available sales evidence")
    return {
        **records.model_dump(),
        "expected_paise": expected,
        "residual_paise": expected - records.bank_credit_paise,
    }
