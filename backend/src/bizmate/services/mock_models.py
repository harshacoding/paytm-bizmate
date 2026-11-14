from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from bizmate.domain.models import Model
from bizmate.domain.types import Count, Identifier, MessageText, Money


class PaymentRecord(Model):
    reference: Identifier
    settlement_reference: Identifier = "settlement-001"
    kind: Literal["sale", "commission", "gst", "refund", "chargeback", "credit"]
    amount_paise: Money
    available_at: AwareDatetime


class CustomerRecord(Model):
    customer_id: Identifier
    marketing_consent: StrictBool


class OrderRecord(Model):
    order_id: Identifier
    customer_id: Identifier
    ordered_at: AwareDatetime
    qualifying: StrictBool = True


class CustomerHistory(Model):
    customers: tuple[CustomerRecord, ...]
    orders: tuple[OrderRecord, ...]
    evaluated_at: AwareDatetime
    simulated: Literal[True] = True


class SettlementReport(Model):
    settlement_reference: Identifier = "settlement-001"
    records: tuple[PaymentRecord, ...]
    captured_at: AwareDatetime
    simulated: Literal[True] = True


class CampaignPayload(Model):
    message: MessageText
    recipient_ids: tuple[Identifier, ...] = Field(min_length=1)
    cost_paise: Money

    @model_validator(mode="after")
    def validate_audience(self):
        if len(set(self.recipient_ids)) != len(self.recipient_ids):
            raise ValueError("Campaign recipients must be unique")
        if self.cost_paise != len(self.recipient_ids) * 200:
            raise ValueError("Synthetic campaign cost must be 200 paise per recipient")
        return self


class ClockState(Model):
    current_time: datetime
    simulated: Literal[True] = True


class ClockAdvance(Model):
    seconds: Count = Field(gt=0)


class FailureControl(Model):
    operation: Literal[
        "get_transactions",
        "get_bank_credits",
        "get_settlement_report",
        "get_refunds_and_chargebacks",
        "fresh_credits",
        "get_customers_and_orders",
        "get_ticket_status",
        "get_campaign_delivery_status",
        "ticket_after_write",
        "campaign_after_write",
    ]
    count: Count = 1


class ConsentControl(Model):
    marketing_consent: StrictBool
