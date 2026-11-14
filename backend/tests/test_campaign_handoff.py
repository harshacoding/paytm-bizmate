"""BM-14/15 acceptance through public APIs and durable synthetic provider records."""

import json
import sqlite3
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from bizmate.api.dependencies import current_context
from bizmate.main import create_app
from bizmate.services.demo import demo_context
from bizmate.services.mock_models import FailureControl, OrderRecord

OFFER = 'Send inactive customers message="Come back for 10% off"'
BANK = "Change my registered bank account"


def create(c, message=OFFER):
    r = c.post("/api/v1/tasks", json={"message": message})
    assert r.status_code == 201, r.text
    return r.json()


def root(t):
    return "/api/v1/tasks/" + t["task_id"]


def approve(c, t):
    a = t["approvals"][-1]
    r = c.post(
        root(t) + "/approvals/" + a["approval_id"],
        json={"decision": "approve", "input_hash": a["input_hash"]},
    )
    assert r.status_code == 200, r.text
    return a


def resume(c, t):
    r = c.post(root(t) + "/resume")
    assert r.status_code == 200, r.text
    return r.json()


def edit(c, t, message="A revised merchant offer", **extra):
    return c.patch(
        root(t) + "/campaign",
        json={"expected_revision": t["revision"], "message": message, **extra},
    )


def actions(c):
    with sqlite3.connect(c.app.state.settings.database_file) as db:
        return db.execute("SELECT action, inputs FROM mock_actions").fetchall()


@pytest.mark.parametrize("approved_first", [False, True])
def test_edit_replaces_snapshot_and_requires_new_approval(persistent_client, approved_first):
    c = persistent_client
    t = create(c)
    old = t["approvals"][-1]
    if approved_first:
        approve(c, t)
        t = c.get(root(t)).json()
    response = edit(c, t, "  Exact edited offer\n")
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["status"] == "AWAITING_APPROVAL"
    assert updated["approvals"][0]["decision"] == "cancelled"
    assert updated["approvals"][0]["approved_inputs"] == old["approved_inputs"]
    new = updated["approvals"][-1]
    assert new["approved_inputs"]["message"] == "  Exact edited offer\n"
    assert new["input_hash"] != old["input_hash"] and new["decision"] == "pending"
    assert not resume(c, updated)["receipts"] and actions(c) == []
    stale = c.post(
        root(t) + "/approvals/" + old["approval_id"],
        json={"decision": "approve", "input_hash": old["input_hash"]},
    )
    assert stale.status_code == 409
    approve(c, updated)
    done = resume(c, updated)
    assert done["status"] == "COMPLETED"
    assert json.loads(actions(c)[0][1])["message"] == "  Exact edited offer\n"
    review = c.get(root(t) + "/campaign").json()
    assert review["simulated"] and not review["editable"]
    assert review["delivery"]["delivered"] == 118 and review["delivery"]["failed"] == 2
    assert review["commercial_outcome"] == "not_measured"
    assert len(actions(c)) == 1


def test_stale_edit_and_client_audience_cost_override_rejected(persistent_client):
    c = persistent_client
    t = create(c)
    assert edit(c, t, expected_revision=t["revision"] - 1).status_code == 409
    for field, value in [
        ("recipient_ids", ["customer-999"]),
        ("cost_paise", 1),
        ("merchant_id", "merchant_other"),
        ("approved", True),
    ]:
        assert edit(c, t, **{field: value}).status_code == 422
    assert c.get(root(t)).json() == t and actions(c) == []


def test_inactivity_window_edit_recomputes_review(persistent_client):
    c = persistent_client
    t = create(c)
    updated = edit(c, t, inactivity_days=45).json()
    assert updated["status"] == "AWAITING_APPROVAL"
    r = c.get(root(t) + "/campaign").json()
    assert 0 < r["eligible_count"] < 120
    assert r["estimated_cost_paise"] == r["eligible_count"] * 200
    assert r["inactivity_days"] == 45
    approve(c, updated)
    assert resume(c, updated)["status"] == "COMPLETED"


@pytest.mark.parametrize("change", ["consent", "recent_order", "new_eligible"])
def test_execution_rechecks_full_audience_and_requests_review(persistent_client, change):
    c = persistent_client
    t = create(c)
    approve(c, t)
    services = c.app.state.mock_services
    ctx = demo_context("merchant_demo")
    if change == "consent":
        services.set_consent(ctx, "customer-001", False)
    elif change == "new_eligible":
        services.advance(ctx, 21 * 86400)
    else:
        order = OrderRecord(
            order_id="new-order",
            customer_id="customer-001",
            ordered_at=services.clock(ctx) - timedelta(days=1),
        )
        with services.store.transaction() as db:
            services.store.put(
                db, ctx.merchant_id, "order", order.order_id, order.model_dump(mode="json")
            )
    updated = resume(c, t)
    assert updated["status"] == "AWAITING_APPROVAL", updated["next_action"]
    assert updated["approvals"][0]["decision"] == "cancelled"
    assert updated["approvals"][-1]["decision"] == "pending"
    assert updated["approvals"][-1]["input_hash"] != t["approvals"][0]["input_hash"]
    assert not updated["receipts"] and actions(c) == []
    segment = updated["workflow_data"]["segment"]
    assert segment["eligible_count"] == (180 if change == "new_eligible" else 119)
    approve(c, updated)
    done = resume(c, updated)
    assert done["status"] == "COMPLETED" and len(actions(c)) == 1
    inputs = json.loads(actions(c)[0][1])
    assert inputs["recipient_ids"] == segment["recipient_ids"]
    assert inputs["cost_paise"] == segment["eligible_count"] * 200


def test_direct_execute_also_rejects_changed_consent_before_claim(persistent_client):
    c = persistent_client
    t = create(c)
    a = approve(c, t)
    c.app.state.mock_services.set_consent(demo_context("merchant_demo"), "customer-001", False)
    r = c.post(
        root(t) + "/approvals/" + a["approval_id"] + "/execute",
        json={"inputs": a["approved_inputs"]},
    )
    assert r.status_code == 409 and actions(c) == []
    assert not c.get(root(t)).json()["tool_executions"][-1]["outcome"] == "uncertain"


def test_campaign_restart_after_edit_timeout_and_replay(persistent_client):
    c = persistent_client
    t = edit(c, create(c), "Durable edited offer").json()
    c.app.state.mock_services.inject_failure(
        demo_context("merchant_demo"), FailureControl(operation="campaign_after_write")
    )
    with TestClient(create_app(c.app.state.settings)) as restarted:
        assert restarted.get(root(t)).json() == t
        approve(restarted, t)
        done = resume(restarted, t)
        assert done["status"] == "COMPLETED"
        assert resume(restarted, done)["receipts"] == done["receipts"]
        assert len(actions(restarted)) == 1
        assert edit(restarted, done).status_code == 409


@pytest.mark.parametrize("merchant_request", [BANK, BANK + " to 1234567890 with PIN 1234"])
def test_handoff_is_minimal_approved_verified_and_pending_human_support(
    persistent_client, merchant_request
):
    c = persistent_client
    t = create(c, merchant_request)
    assert t["status"] == "AWAITING_APPROVAL" and len(t["capability_gaps"]) == 1
    review = c.get(root(t) + "/handoff").json()
    assert review["draft"]["requested_capability"] == "bank_account_change"
    assert review["draft"]["required_information"] == []
    assert review["draft"]["routing"] == "merchant_support"
    assert "1234567890" not in review["draft"]["summary"]
    assert "1234" not in t["approvals"][0]["approved_inputs"]["summary"]
    assert review["routing_status"] == "awaiting_approval"
    assert not resume(c, t)["receipts"] and actions(c) == []
    approve(c, t)
    done = resume(c, t)
    assert done["status"] == "ESCALATED"
    review = c.get(root(t) + "/handoff").json()
    assert review["routing_status"] == "verified"
    assert review["requested_change_status"] == "pending_human_support"
    assert review["gaps"][0]["handoff_reference"] == review["receipt"]["external_reference"]
    assert review["verification"]["tool_name"] == "get_ticket_status"
    assert [a[0] for a in actions(c)] == ["create_support_ticket"]
    assert "bank_account_change" not in c.app.state.tools._tools
    assert resume(c, done) == done


def test_permission_gap_routes_only_if_support_permission_exists(persistent_client):
    c = persistent_client
    ctx = demo_context("merchant_demo").with_updates(
        scopes=["tasks:read", "tasks:write", "tasks:approve", "tickets:write"]
    )
    c.app.dependency_overrides[current_context] = lambda: ctx
    t = create(c)
    assert t["status"] == "AWAITING_APPROVAL" and t["intent"] == "handoff"
    r = c.get(root(t) + "/handoff").json()
    assert r["draft"]["reason"] == "permission_denied" and r["gaps"]
    assert "send_campaign" not in [s["tool_name"] for s in t["plan"]]
    approve(c, t)
    done = resume(c, t)
    assert done["status"] == "ESCALATED"
    assert [a[0] for a in actions(c)] == ["create_support_ticket"]


def test_permission_gap_without_support_access_does_not_invent_reference(persistent_client):
    c = persistent_client
    c.app.dependency_overrides[current_context] = lambda: demo_context("merchant_other")
    t = create(c, BANK)
    assert t["status"] == "ESCALATED"
    r = c.get(root(t) + "/handoff").json()
    assert r["routing_status"] == "unavailable" and r["receipt"] is None
    assert t["capability_gaps"] and not t["approvals"] and actions(c) == []


@pytest.mark.parametrize("operation", ["ticket_after_write", "get_ticket_status"])
def test_handoff_uncertainty_and_failed_verification_survive_restart(persistent_client, operation):
    c = persistent_client
    t = create(c, BANK)
    c.app.state.mock_services.inject_failure(
        demo_context("merchant_demo"),
        FailureControl(operation=operation, count=1 if operation == "ticket_after_write" else 3),
    )
    approve(c, t)
    done = resume(c, t)
    assert done["status"] == "ESCALATED" and len(actions(c)) == 1
    with TestClient(create_app(c.app.state.settings)) as restarted:
        review = restarted.get(root(t) + "/handoff").json()
        assert review["routing_status"] == (
            "verified" if operation == "ticket_after_write" else "unverified"
        )
        assert review["requested_change_status"] == "pending_human_support"
        assert resume(restarted, done) == done
        assert len(actions(restarted)) == 1


def test_review_ownership_and_readonly_scope(persistent_client):
    c = persistent_client
    campaign, handoff = create(c), create(c, BANK)
    c.app.dependency_overrides[current_context] = lambda: demo_context("merchant_other")
    assert c.get(root(campaign) + "/campaign").status_code == 404
    assert c.get(root(handoff) + "/handoff").status_code == 404
    assert edit(c, campaign).status_code == 404
    c.app.dependency_overrides[current_context] = lambda: demo_context(
        "merchant_demo"
    ).with_updates(scopes=["tasks:read"])
    assert c.get(root(campaign) + "/campaign").status_code == 200
    assert c.get(root(handoff) + "/handoff").status_code == 200
    assert edit(c, campaign).status_code == 403


def test_change_between_policy_check_and_provider_write_is_blocked(persistent_client, monkeypatch):
    c = persistent_client
    t = create(c)
    approve(c, t)
    services = c.app.state.mock_services
    original = services.prepare_campaign

    def revoke_after_claim(context, task_id, payload):
        digest = original(context, task_id, payload)
        services.set_consent(context, "customer-001", False)
        return digest

    monkeypatch.setattr(services, "prepare_campaign", revoke_after_claim)
    done = resume(c, t)
    assert done["status"] == "ESCALATED" and actions(c) == []
    assert not done["receipts"]
    # The dispatcher cannot infer provider non-commit from an exception. Preserve the
    # uncertain claim for manual inspection and never retry the write.
    assert any(e["outcome"] == "uncertain" for e in done["tool_executions"])


def test_preparation_race_refreshes_without_sticking_running(persistent_client, monkeypatch):
    c = persistent_client
    services = c.app.state.mock_services
    original = services.campaign_audience_current
    calls = []

    def changed_once(context, inputs):
        if not calls:
            calls.append(1)
            services.set_consent(context, "customer-001", False)
        return original(context, inputs)

    # Registry stores the callable at startup, so replace the backend precondition itself.
    from dataclasses import replace

    registry = c.app.state.tools
    definition = registry._tools["send_campaign"]
    registry._tools["send_campaign"] = replace(
        definition, preconditions=(("campaign_audience_current", changed_once),)
    )
    t = create(c)
    assert t["status"] == "AWAITING_APPROVAL"
    assert t["workflow_data"]["segment"]["eligible_count"] == 119
    assert actions(c) == []


def test_support_reference_without_matching_route_is_not_a_confirmed_handoff(
    persistent_client, monkeypatch
):
    c = persistent_client
    t = create(c, BANK)
    approve(c, t)
    services = c.app.state.mock_services
    original = services.create

    def wrong_route(*args, **kwargs):
        receipt = original(*args, **kwargs)
        with services.store.transaction() as db:
            db.execute(
                "UPDATE mock_actions SET result=? WHERE reference=?",
                (json.dumps({"status": "open", "routing": "unknown"}), receipt.external_reference),
            )
        return receipt

    monkeypatch.setattr(services, "create", wrong_route)
    done = resume(c, t)
    assert done["status"] == "ESCALATED" and len(done["receipts"]) == 1
    r = c.get(root(t) + "/handoff").json()
    assert r["routing_status"] == "unverified"
    assert r["requested_change_status"] == "pending_human_support"
    assert not any(v["verified"] for v in done["verifications"])


def test_unprepared_campaign_audience_remains_unknown(persistent_client):
    c = persistent_client
    t = create(c, "Send an offer to inactive customers")
    assert t["status"] == "AWAITING_INPUT"
    r = c.get(root(t) + "/campaign").json()
    assert r["eligible_count"] is None and r["estimated_cost_paise"] is None
    updated = edit(c, t, "My exact offer").json()
    assert updated["status"] == "AWAITING_APPROVAL"
    assert c.get(root(t) + "/campaign").json()["eligible_count"] == 120


def test_handoff_cancel_creates_no_ticket(persistent_client):
    c = persistent_client
    t = create(c, BANK)
    a = t["approvals"][-1]
    r = c.post(
        root(t) + "/approvals/" + a["approval_id"],
        json={"decision": "cancel", "input_hash": a["input_hash"]},
    )
    assert r.status_code == 200
    assert c.get(root(t) + "/handoff").json()["routing_status"] == "cancelled"
    assert resume(c, t)["status"] == "AWAITING_INPUT" and actions(c) == []


def test_no_remaining_eligible_customers_saves_empty_audience_without_sending(persistent_client):
    c = persistent_client
    t = create(c)
    approve(c, t)
    with c.app.state.mock_services.store.transaction() as db:
        rows = db.execute(
            "SELECT reference,payload FROM mock_records WHERE merchant_id=? AND kind='customer'",
            ("merchant_demo",),
        ).fetchall()
        for row in rows:
            payload = json.loads(row["payload"])
            payload["marketing_consent"] = False
            db.execute(
                "UPDATE mock_records SET payload=? WHERE merchant_id=? "
                "AND kind='customer' AND reference=?",
                (json.dumps(payload), "merchant_demo", row["reference"]),
            )
    done = resume(c, t)
    assert done["status"] == "ESCALATED" and actions(c) == []
    review = c.get(root(t) + "/campaign").json()
    assert review["eligible_count"] == 0 and review["estimated_cost_paise"] == 0
    assert review["approval"] is None and review["delivery"] is None
