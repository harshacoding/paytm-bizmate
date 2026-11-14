from datetime import UTC, datetime, timedelta

from bizmate.services.models import Customer, Order, Segment


def segment_inactive_customers(
    customers: list[Customer],
    orders: list[Order],
    current_time: datetime,
    inactivity_days: int = 30,
) -> Segment:
    if inactivity_days <= 0:
        raise ValueError("Inactivity days must be positive")
    current_time = current_time.replace(tzinfo=current_time.tzinfo or UTC)
    cutoff = current_time - timedelta(days=inactivity_days)
    latest: dict[str, datetime] = {}
    for order in orders:
        ordered_at = order.ordered_at.replace(tzinfo=order.ordered_at.tzinfo or UTC)
        if order.qualifying and ordered_at <= current_time:
            latest[order.customer_id] = max(latest.get(order.customer_id, ordered_at), ordered_at)
    recipients = sorted(
        {
            customer.customer_id
            for customer in customers
            if customer.marketing_consent
            and customer.customer_id in latest
            and latest[customer.customer_id] <= cutoff
        }
    )
    return Segment(
        analysed_count=len(customers),
        inactivity_days=inactivity_days,
        recipient_ids=recipients,
        cost_paise=len(recipients) * 200,
        evaluated_at=current_time,
    )
