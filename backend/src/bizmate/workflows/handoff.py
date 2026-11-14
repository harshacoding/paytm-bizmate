"""Minimal support drafts. Capability gaps never authorize a workaround."""

from bizmate.domain.context import require_context
from bizmate.domain.models import CapabilityGap, Scope, new_id
from bizmate.workflows.review import HandoffDraft


class CapabilityUnavailable(PermissionError):
    def __init__(self, capability, *, reason="permission_denied"):
        self.capability, self.reason = capability, reason
        super().__init__("The requested capability is unavailable for this merchant")


def prepare_handoff(
    context, task, *, capability="bank_account_change", reason="missing_capability"
):
    require_context(context)
    context.require(Scope.TASKS_READ, Scope.TASKS_WRITE)
    context.require_owner(task.merchant_id)
    summary = (
        "Request human support for a registered bank-account change. "
        "The account change is pending with support."
        if capability == "bank_account_change"
        else f"Request human review of unavailable capability: {capability}. "
        "The original action has not been performed."
    )
    draft = HandoffDraft(requested_capability=capability, reason=reason, summary=summary)
    existing = next((g for g in task.capability_gaps if g.requested_capability == capability), None)
    gap = existing or CapabilityGap(
        task_id=task.task_id,
        merchant_id=context.merchant_id,
        gap_id=new_id(),
        requested_capability=capability,
        reason="The capability is unavailable in this application."
        if reason == "missing_capability"
        else "The current merchant does not have permission for this capability.",
    )
    return draft, gap
