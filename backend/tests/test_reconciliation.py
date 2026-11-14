from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from bizmate.api.dependencies import current_context
from bizmate.domain.errors import AccessDenied
from bizmate.domain.models import Intent
from bizmate.domain.types import MAX_SAFE_INTEGER
from bizmate.services.demo import MERCHANTS, demo_context
from bizmate.services.mock_models import PaymentRecord, SettlementReport
from bizmate.workflows.settlement import reconcile_settlement

STAMP = datetime(2026, 11, 14, 4, tzinfo=UTC)


def records():
    return tuple(
        PaymentRecord(reference=f"{kind}-1", kind=kind, amount_paise=amount, available_at=STAMP)
        for kind, amount in [
            ("sale", 2000000),
            ("commission", 24000),
            ("gst", 4320),
            ("refund", 80000),
            ("chargeback", 35000),
            ("credit", 1840000),
        ]
    )


def proof(rows):
    return reconcile_settlement(
        demo_context("merchant_demo"), SettlementReport(records=rows, captured_at=STAMP)
    )


def test_exact_integer_proof_and_complete_source_links():
    result = proof(records())
    assert result.status == "complete"
    assert result.sales.amount_paise == 2000000
    assert result.expected.amount_paise == 1856680
    assert result.credit.amount_paise == 1840000
    assert result.residual.amount_paise == 16680
    refs = {record.reference for record in result.sources}
    for name in [
        "sales",
        "commission",
        "gst",
        "refunds",
        "chargeback",
        "credit",
        "expected",
        "residual",
    ]:
        line = getattr(result, name)
        assert line.status == "known" and line.source_references
        assert set(line.source_references) <= refs
    assert proof(tuple(reversed(records()))) == result
    assert proof((*records(), records()[0])) == result


@pytest.mark.parametrize(
    "kind,field",
    [
        ("sale", "sales"),
        ("commission", "commission"),
        ("gst", "gst"),
        ("refund", "refunds"),
        ("chargeback", "chargeback"),
        ("credit", "credit"),
    ],
)
def test_missing_evidence_is_unknown_not_zero(kind, field):
    result = proof(tuple(row for row in records() if row.kind != kind))
    assert result.status == "incomplete"
    assert getattr(result, field).amount_paise is None
    assert result.residual.amount_paise is None
    assert (
        (result.expected.amount_paise == 1856680)
        if kind == "credit"
        else (result.expected.amount_paise is None)
    )


def test_explicit_zero_evidence_is_known_and_empty_report_is_unknown():
    rows = tuple(
        row.with_updates(amount_paise=0) if row.kind == "refund" else row for row in records()
    )
    result = proof(rows)
    assert result.refunds.status == "known" and result.refunds.amount_paise == 0
    assert result.expected.amount_paise == 1936680
    empty = proof(())
    assert empty.status == "incomplete" and empty.residual.amount_paise is None


def test_conflicting_references_never_double_count_or_claim_known_result():
    result = proof((*records(), records()[0].with_updates(amount_paise=1999999)))
    assert result.status == "conflicting"
    assert result.sales.amount_paise is None and result.residual.amount_paise is None
    assert result.warnings
    cross_kind = proof((*records(), records()[0].with_updates(kind="refund")))
    assert cross_kind.sales.status == cross_kind.refunds.status == "conflicting"


def test_other_settlements_future_records_and_overcredits():
    result = proof(
        (
            *records(),
            records()[0].with_updates(reference="other-sale", settlement_reference="other"),
            records()[0].with_updates(
                reference="future-sale", available_at=STAMP + timedelta(days=1)
            ),
        )
    )
    assert result.residual.amount_paise == 16680 and result.warnings
    rows = tuple(
        row.with_updates(amount_paise=1900000) if row.kind == "credit" else row for row in records()
    )
    assert proof(rows).residual.amount_paise == -43320


def test_exact_range_overflow_remains_unknown():
    rows = (
        *records(),
        records()[0].with_updates(reference="huge-sale", amount_paise=MAX_SAFE_INTEGER),
    )
    result = proof(rows)
    assert result.status == "conflicting" and result.sales.amount_paise is None
    assert result.residual.amount_paise is None


@pytest.mark.parametrize("value", [True, "16680", 16680.5, -1])
def test_money_cannot_be_coerced(value):
    with pytest.raises(ValidationError):
        records()[0].with_updates(amount_paise=value)


def test_context_and_permissions_cannot_be_supplied_as_merchant_metadata():
    report = SettlementReport(records=records(), captured_at=STAMP)
    for context in [
        MERCHANTS["merchant_demo"],
        demo_context("merchant_demo").with_updates(scopes=[]),
    ]:
        with pytest.raises(AccessDenied):
            reconcile_settlement(context, report)


def test_api_registry_seeded_figures_and_no_task_side_effect(persistent_client):
    client = persistent_client
    before = client.get("/api/v1/tasks").json()
    response = client.post("/api/v1/settlements/reconcile", json={})
    assert response.status_code == 200
    result = response.json()
    assert result["residual"]["amount_paise"] == 16680
    assert result["expected"]["amount_paise"] == 1856680
    assert result["credit"]["amount_paise"] == 1840000
    assert len(result["sales"]["source_references"]) == 200
    assert result["simulated"] is True
    assert client.get("/api/v1/tasks").json() == before
    assert (
        client.app.state.tools.execute(
            "reconcile_settlement", demo_context("merchant_demo"), {}
        ).model_dump(mode="json")
        == result
    )
    assert any(
        tool.metadata.name == "reconcile_settlement"
        for tool in client.app.state.tools.discover(
            demo_context("merchant_demo"), intent=Intent.SETTLEMENT
        )
    )
    missing = client.post(
        "/api/v1/settlements/reconcile", json={"settlement_reference": "missing"}
    ).json()
    assert missing["status"] == "incomplete" and missing["residual"]["amount_paise"] is None
    client.post("/api/v1/demo/clock/advance", json={"seconds": 86400})
    fresh = client.post("/api/v1/settlements/reconcile", json={}).json()
    assert fresh["credit"]["amount_paise"] == 1856680 and fresh["residual"]["amount_paise"] == 0


def test_api_scope_isolation_and_timeout(persistent_client):
    client = persistent_client
    assert (
        client.post("/api/v1/settlements/reconcile", json={"merchant_id": "forged"}).status_code
        == 422
    )
    result = client.post(
        "/api/v1/settlements/reconcile?merchant_id=merchant_other",
        headers={"X-Merchant-Id": "merchant_other"},
        json={},
    ).json()
    assert result["merchant_id"] == "merchant_demo"
    client.app.dependency_overrides[current_context] = lambda: demo_context(
        "merchant_demo"
    ).with_updates(scopes=[])
    assert client.post("/api/v1/settlements/reconcile", json={}).status_code == 403
    client.app.dependency_overrides.clear()
    client.post("/api/v1/demo/failures", json={"operation": "get_settlement_report"})
    assert client.post("/api/v1/settlements/reconcile", json={}).status_code == 503
    client.app.dependency_overrides[current_context] = lambda: demo_context("merchant_other")
    assert (
        client.post("/api/v1/settlements/reconcile", json={}).json()["merchant_id"]
        == "merchant_other"
    )
