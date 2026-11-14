from bizmate.domain.errors import FeaturePending
from bizmate.domain.models import Approval, Merchant
from bizmate.services.mocks import action_hash


def require_approval_engine() -> None:
    """BM-06: replace with exact-input, actor, scope and idempotency checks plus receipts."""
    raise FeaturePending("BM-06", "Approval and verified execution are not implemented yet.")


def validate_approved_action(
    approval: Approval | None, merchant: Merchant, action: str, inputs: dict
):
    if approval is None:
        require_approval_engine()
    if (
        approval.decision != "approved"
        or approval.merchant_id != merchant.merchant_id
        or approval.action != action
        or approval.task_id != inputs.get("task_id")
        or approval.approved_inputs != inputs
        or approval.input_hash != action_hash(action, inputs)
    ):
        raise PermissionError("The action requires a matching approved snapshot")
