"""Typed backend contracts for BM-14/15, independent of BM-09 presentation."""

from typing import Literal

from pydantic import Field

from bizmate.domain.models import Approval, CapabilityGap, Model, Receipt, Verification
from bizmate.domain.types import Count, Identifier, MessageText, Money, ShortText, Text
from bizmate.tools.mock_tools import CampaignDelivery


class CampaignEdit(Model):
    expected_revision: int = Field(strict=True, ge=1)
    message: MessageText
    inactivity_days: int | None = Field(default=None, strict=True, ge=1, le=3650)


class CampaignReview(Model):
    task_id: Identifier
    merchant_id: Identifier
    revision: int
    message: MessageText | None
    inactivity_days: int
    recipient_ids: tuple[Identifier, ...]
    eligible_count: Count | None
    estimated_cost_paise: Money | None
    approval: Approval | None
    receipt: Receipt | None
    verification: Verification | None
    delivery: CampaignDelivery | None
    editable: bool
    simulated: Literal[True] = True
    commercial_outcome: Literal["not_measured"] = "not_measured"


class HandoffDraft(Model):
    requested_capability: ShortText
    reason: Literal["missing_capability", "permission_denied"]
    summary: Text
    routing: Literal["merchant_support"] = "merchant_support"
    # Support can identify the synthetic merchant through trusted context. Bank details,
    # credentials and contact details are neither collected nor copied into the ticket.
    required_information: tuple[str, ...] = ()
    simulated: Literal[True] = True


class HandoffReview(Model):
    task_id: Identifier
    merchant_id: Identifier
    revision: int
    draft: HandoffDraft
    explanation: Text
    gaps: tuple[CapabilityGap, ...]
    approval: Approval | None
    receipt: Receipt | None
    verification: Verification | None
    routing_status: Literal[
        "awaiting_approval", "approved", "cancelled", "unavailable", "unverified", "verified"
    ]
    requested_change_status: Literal["pending_human_support"] = "pending_human_support"
    simulated: Literal[True] = True
