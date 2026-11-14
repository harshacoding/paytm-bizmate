from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, Field

from bizmate.domain.context import MerchantContext, require_context
from bizmate.domain.models import Model, Scope
from bizmate.domain.types import Count, Identifier, Money
from bizmate.services.mock_models import CustomerHistory
from bizmate.services.mocks import MockServices


class SegmentRequest(Model):
    inactivity_days: Count = Field(default=30, gt=0)


class CustomerSegment(Model):
    merchant_id: Identifier
    evaluated_at: AwareDatetime
    inactivity_days: Count
    histories_analysed: Count
    inactive_count: Count
    eligible_count: Count
    excluded_without_consent: Count
    excluded_unknown_history: Count
    recipient_ids: tuple[Identifier, ...]
    unit_cost_paise: Money = 200
    estimated_cost_paise: Money
    simulated: Literal[True] = True


def segment_inactive_customers(
    context: MerchantContext, history: CustomerHistory, inactivity_days: int = 30
) -> CustomerSegment:
    """Include an inactivity boundary exactly, using the latest qualifying order in UTC."""
    require_context(context)
    context.require(Scope.CUSTOMERS_READ)
    window = SegmentRequest(inactivity_days=inactivity_days).inactivity_days
    history = CustomerHistory.model_validate(history)
    evaluated_at = history.evaluated_at.astimezone(UTC)
    customers = {customer.customer_id: customer for customer in history.customers}
    if len(customers) != len(history.customers):
        raise ValueError("Duplicate customer records make segmentation ambiguous")
    if len({order.order_id for order in history.orders}) != len(history.orders):
        raise ValueError("Duplicate order records make segmentation ambiguous")
    latest: dict[str, datetime] = {}
    future: set[str] = set()
    for order in history.orders:
        if order.customer_id not in customers or not order.qualifying:
            continue
        ordered_at = order.ordered_at.astimezone(UTC)
        if ordered_at > evaluated_at:
            future.add(order.customer_id)
            continue
        latest[order.customer_id] = max(latest.get(order.customer_id, ordered_at), ordered_at)
    # Missing/future-only history is unknown. It cannot establish inactivity.
    known = set(latest) - future
    inactive = {
        customer_id for customer_id in known if (evaluated_at - latest[customer_id]).days >= window
    }
    recipients = tuple(
        sorted(customer_id for customer_id in inactive if customers[customer_id].marketing_consent)
    )
    return CustomerSegment(
        merchant_id=context.merchant_id,
        evaluated_at=evaluated_at,
        inactivity_days=window,
        histories_analysed=len(customers),
        inactive_count=len(inactive),
        eligible_count=len(recipients),
        excluded_without_consent=len(inactive) - len(recipients),
        excluded_unknown_history=len(customers) - len(known),
        recipient_ids=recipients,
        estimated_cost_paise=len(recipients) * 200,
    )


def prepare_customer_segment(
    context: MerchantContext, services: MockServices, request: SegmentRequest
) -> CustomerSegment:
    require_context(context)
    context.require(Scope.CUSTOMERS_READ)
    request = SegmentRequest.model_validate(request)
    return segment_inactive_customers(context, services.customers(context), request.inactivity_days)
