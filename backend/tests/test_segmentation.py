from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from bizmate.api.dependencies import current_context
from bizmate.config import Settings
from bizmate.domain.errors import AccessDenied
from bizmate.domain.models import Intent, Scope
from bizmate.services.demo import MERCHANTS, demo_context
from bizmate.services.mock_models import CustomerHistory, CustomerRecord, OrderRecord
from bizmate.workflows.campaign import SegmentRequest, segment_inactive_customers

STAMP = datetime(2026, 11, 14, 4, tzinfo=UTC)


def history(orders, *, consent=True):
    return CustomerHistory(
        customers=(CustomerRecord(customer_id="customer-a", marketing_consent=consent),),
        orders=tuple(orders),
        evaluated_at=STAMP,
    )


def order(days, *, order_id="order-a", qualifying=True):
    return OrderRecord(
        order_id=order_id,
        customer_id="customer-a",
        ordered_at=STAMP - timedelta(days=days),
        qualifying=qualifying,
    )


@pytest.mark.parametrize(
    "elapsed, eligible",
    [
        (timedelta(days=30), True),
        (timedelta(days=30, microseconds=-1), False),
        (timedelta(days=30, microseconds=1), True),
        (timedelta(days=29), False),
    ],
)
def test_exact_inactivity_boundary(elapsed, eligible):
    record = order(30).with_updates(ordered_at=STAMP - elapsed)
    result = segment_inactive_customers(demo_context("merchant_demo"), history([record]))
    assert result.eligible_count == int(eligible)
    assert result.estimated_cost_paise == int(eligible) * 200


def test_latest_qualifying_order_wins_and_ordering_is_deterministic():
    context = demo_context("merchant_demo")
    old, recent = order(45), order(10, order_id="recent")
    assert segment_inactive_customers(context, history([old, recent])).eligible_count == 0
    assert segment_inactive_customers(context, history([recent, old])).eligible_count == 0
    cancelled = recent.with_updates(qualifying=False)
    assert segment_inactive_customers(context, history([cancelled, old])).eligible_count == 1


def test_missing_future_and_nonconsenting_customers_are_excluded():
    context = demo_context("merchant_demo")
    for data in [
        history([]),
        history([order(-1)]),
        history([order(45), order(-1, order_id="future")]),
    ]:
        result = segment_inactive_customers(context, data)
        assert result.excluded_unknown_history == 1 and result.eligible_count == 0
    result = segment_inactive_customers(context, history([order(45)], consent=False))
    assert result.inactive_count == 1
    assert result.excluded_without_consent == 1
    assert result.recipient_ids == () and result.estimated_cost_paise == 0


def test_timezone_offsets_and_custom_windows_are_exact():
    data = history([order(30).with_updates(ordered_at="2026-10-15T09:30:00+05:30")])
    context = demo_context("merchant_demo")
    assert segment_inactive_customers(context, data).eligible_count == 1
    assert segment_inactive_customers(context, data, 31).eligible_count == 0
    assert segment_inactive_customers(context, data, 1).eligible_count == 1
    assert segment_inactive_customers(context, data, 9007199254740991).eligible_count == 0


@pytest.mark.parametrize("days", [0, -1, True, False, 30.5, "30", None, 9007199254740992])
def test_invalid_windows_are_rejected(days):
    with pytest.raises(ValidationError):
        SegmentRequest(inactivity_days=days)


def test_duplicate_records_cannot_produce_an_ambiguous_audience():
    data = history([order(40)])
    context = demo_context("merchant_demo")
    for invalid in [
        data.with_updates(customers=(*data.customers, *data.customers)),
        data.with_updates(orders=(*data.orders, *data.orders)),
    ]:
        with pytest.raises(ValueError, match="Duplicate"):
            segment_inactive_customers(context, invalid)


def test_unmatched_orders_cannot_add_recipients_and_empty_history_costs_zero():
    context = demo_context("merchant_demo")
    unknown = order(40).with_updates(customer_id="unknown")
    result = segment_inactive_customers(context, history([unknown]))
    assert result.eligible_count == 0
    empty = CustomerHistory(customers=(), orders=(), evaluated_at=STAMP)
    assert segment_inactive_customers(context, empty).estimated_cost_paise == 0
    for bad_context in [
        MERCHANTS["merchant_demo"],
        demo_context("merchant_demo").with_updates(scopes=[]),
    ]:
        with pytest.raises(AccessDenied):
            segment_inactive_customers(bad_context, empty)


def test_api_and_registry_produce_seeded_segment_without_writing(persistent_client):
    client = persistent_client
    before = client.get("/api/v1/tasks").json()
    response = client.post("/api/v1/campaigns/segment", json={})
    assert response.status_code == 200
    result = response.json()
    assert result["histories_analysed"] == 200
    assert result["inactive_count"] == result["eligible_count"] == 120
    assert result["unit_cost_paise"] == 200
    assert result["estimated_cost_paise"] == 24000
    assert result["simulated"] is True
    assert result["recipient_ids"] == sorted(result["recipient_ids"])
    assert client.post("/api/v1/campaigns/segment", json={}).json() == result
    registered = client.app.state.tools.execute(
        "segment_inactive_customers", demo_context("merchant_demo"), {}
    )
    assert registered.model_dump(mode="json") == result
    discovered = client.app.state.tools.discover(
        demo_context("merchant_demo"), intent=Intent.WIN_BACK
    )
    assert any(tool.metadata.name == "segment_inactive_customers" for tool in discovered)
    assert client.get("/api/v1/tasks").json() == before
    assert (
        client.post("/api/v1/campaigns/segment", json={"inactivity_days": 61}).json()[
            "estimated_cost_paise"
        ]
        == 0
    )


def test_api_rejects_authority_overrides_and_missing_scope(persistent_client):
    client = persistent_client
    assert (
        client.post("/api/v1/campaigns/segment", json={"merchant_id": "merchant_other"}).status_code
        == 422
    )
    assert (
        client.post("/api/v1/campaigns/segment", json={"inactivity_days": True}).status_code == 422
    )
    result = client.post(
        "/api/v1/campaigns/segment?merchant_id=merchant_other",
        headers={"X-Merchant-Id": "merchant_other"},
        json={},
    ).json()
    assert result["merchant_id"] == "merchant_demo"
    client.app.dependency_overrides[current_context] = lambda: demo_context("merchant_other")
    assert client.post("/api/v1/campaigns/segment", json={}).status_code == 403


def test_consent_and_demo_clock_are_reloaded_each_time(persistent_client):
    client = persistent_client
    client.patch("/api/v1/demo/customers/customer-001/consent", json={"marketing_consent": False})
    result = client.post("/api/v1/campaigns/segment", json={}).json()
    assert result["eligible_count"] == 119 and result["estimated_cost_paise"] == 23800
    assert result["excluded_without_consent"] == 1
    assert "customer-001" not in result["recipient_ids"]
    client.post("/api/v1/demo/clock/advance", json={"seconds": 20 * 86400})
    result = client.post("/api/v1/campaigns/segment", json={}).json()
    assert result["eligible_count"] == 179
    assert result["excluded_without_consent"] == 21
    client.post("/api/v1/demo/failures", json={"operation": "get_customers_and_orders"})
    assert client.post("/api/v1/campaigns/segment", json={}).status_code == 503


def test_merchant_isolation_and_restart_preserve_segmentation_inputs(persistent_client):
    from bizmate.main import create_app

    client = persistent_client
    first = client.post("/api/v1/campaigns/segment", json={}).json()
    settings = client.app.state.settings
    with TestClient(
        create_app(
            Settings(
                _env_file=None,
                database_path=settings.database_path,
                demo_merchant_id="merchant_other",
            )
        )
    ) as other:
        context = demo_context("merchant_other").with_updates(
            scopes=[Scope.CUSTOMERS_READ, Scope.TASKS_READ]
        )
        other.app.dependency_overrides[current_context] = lambda: context
        with other.app.state.mock_services.store.transaction() as connection:
            other.app.state.mock_services.store.put(
                connection,
                "merchant_other",
                "customer",
                "customer-001",
                {"customer_id": "customer-001", "marketing_consent": False},
            )
        result = other.post("/api/v1/campaigns/segment", json={}).json()
        assert result["merchant_id"] == "merchant_other" and result["eligible_count"] == 119
    with TestClient(create_app(settings)) as restarted:
        assert restarted.post("/api/v1/campaigns/segment", json={}).json() == first
