from datetime import datetime
from typing import Literal

from pydantic import Field

from bizmate.domain.models import Message, Model, Money


class Customer(Model):
    customer_id: str
    marketing_consent: bool


class Order(Model):
    order_id: str
    customer_id: str
    ordered_at: datetime
    qualifying: bool = True


class Segment(Model):
    analysed_count: int
    inactivity_days: int
    recipient_ids: list[str]
    unit_cost_paise: Money = 200
    cost_paise: Money
    evaluated_at: datetime


class CampaignDraft(Model):
    message: Message
    inactivity_days: int = Field(default=30, strict=True, gt=0)


class CampaignInputs(Model):
    task_id: str
    message: Message
    recipient_ids: list[str] = Field(min_length=1)
    cost_paise: Money


class HandoffDraft(Model):
    requested_capability: Message = "change_registered_bank_account"
    summary: Message


class TicketInputs(Model):
    task_id: str
    summary: Message


class ClockAdvance(Model):
    seconds: int = Field(strict=True, gt=0)


class ClockState(Model):
    current_time: datetime
    simulated: Literal[True] = True


class FailureControl(Model):
    operation: Literal[
        "settlement_report",
        "ticket_after_write",
        "campaign_after_write",
        "ticket_status",
        "campaign_delivery",
        "fresh_credits",
    ]
    count: int = Field(default=1, strict=True, ge=0)


class ConsentChange(Model):
    marketing_consent: bool


class SettlementRecords(Model):
    settlement_reference: str
    sales_paise: Money
    commission_paise: Money
    gst_paise: Money
    refunds_paise: Money
    chargeback_paise: Money
    bank_credit_paise: Money
    bank_credit_reference: str


class Credit(Model):
    reference: str
    settlement_reference: str
    amount_paise: Money
    available_at: datetime


class SettlementFollowup(Model):
    settlement_reference: str
    outstanding_paise: int = Field(strict=True, gt=0)
    baseline_credit_reference: str
    evidence_after: datetime
