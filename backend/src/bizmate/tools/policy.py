from bizmate.domain.errors import FeaturePending


def require_approval_engine() -> None:
    """BM-06: replace with exact-input, actor, scope and idempotency checks plus receipts."""
    raise FeaturePending("BM-06", "Approval and verified execution are not implemented yet.")
