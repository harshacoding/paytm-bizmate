import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from bizmate.config import Settings
from bizmate.domain.errors import AccessDenied
from bizmate.domain.lifecycle import transition_task
from bizmate.domain.models import Intent, Task, TaskStatus
from bizmate.main import create_app
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import MERCHANTS, demo_context
from bizmate.services.mock_models import CampaignPayload, FailureControl
from bizmate.services.mock_store import DEMO_START, MockConflictError, MockTimeout, SQLiteMockStore
from bizmate.services.mocks import MockServices
from bizmate.tools.mock_tools import register_mock_tools
from bizmate.tools.registry import ToolRegistry


@pytest.fixture
def providers(tmp_path):
    path = tmp_path / "mocks.sqlite3"
    tasks = SQLiteTaskRepository(path)
    services = MockServices(SQLiteMockStore(path), tasks, controls_enabled=True)
    context = demo_context("merchant_demo")
    task = tasks.save(
        context,
        Task(
            merchant_id=context.merchant_id,
            goal="Test synthetic services",
            original_request="Investigate",
            next_action="Read fixtures",
        ),
    )
    return services, context, task


def prepare_campaign(services, context, task):
    payload = CampaignPayload(
        message="Come back for a synthetic offer",
        recipient_ids=tuple(
            customer.customer_id for customer in services.customers(context).customers[:120]
        ),
        cost_paise=24000,
    )
    return services.prepare_campaign(context, task.task_id, payload)


def test_seeded_financial_and_campaign_ground_truth(providers):
    services, context, task = providers
    report = services.report(context)
    amounts = {
        kind: sum(row.amount_paise for row in report.records if row.kind == kind)
        for kind in ["sale", "commission", "gst", "refund", "chargeback", "credit"]
    }
    expected = amounts["sale"] - sum(
        amounts[kind] for kind in ["commission", "gst", "refund", "chargeback"]
    )
    assert amounts["sale"] == 2000000 and expected == 1856680
    assert expected - amounts["credit"] == 16680
    assert len(services.transactions(context)) == 200
    assert len(services.deductions(context)) == 4
    evidence = services.records(context, task.task_id)
    assert all(
        item.merchant_id == context.merchant_id and item.task_id == task.task_id
        for item in evidence
    )
    history = services.customers(context)
    cutoff = history.evaluated_at - timedelta(days=30)
    inactive = {
        order.customer_id
        for order in history.orders
        if order.qualifying and order.ordered_at <= cutoff
    }
    eligible = [
        customer
        for customer in history.customers
        if customer.marketing_consent and customer.customer_id in inactive
    ]
    assert len(history.customers) == 200 and len(eligible) == 120
    assert len(eligible) * 200 == 24000
    assert history.orders[0].ordered_at == cutoff


def test_ticket_and_delivery_are_persisted_and_independently_read(providers):
    services, context, task = providers
    ticket = services.create(context, task.task_id, "Investigate missing credit", "ticket-key")
    digest = prepare_campaign(services, context, task)
    campaign = services.send(context, task.task_id, digest, "campaign-key")
    restarted = MockServices(
        SQLiteMockStore(services.store.path), SQLiteTaskRepository(services.store.path)
    )
    assert restarted.status(context, ticket.external_reference) == "open"
    assert restarted.delivery(context, campaign.external_reference) == {
        "delivered": 118,
        "failed": 2,
    }
    assert restarted.lookup(context, "send_campaign", "campaign-key") == campaign
    with services.store.transaction() as connection:
        connection.execute(
            "UPDATE mock_actions SET result = ? WHERE reference = ?",
            (json.dumps({"delivered": 117, "failed": 3}), campaign.external_reference),
        )
    assert restarted.delivery(context, campaign.external_reference) == {
        "delivered": 117,
        "failed": 3,
    }


def test_concurrent_writes_are_idempotent_and_changed_inputs_conflict(providers):
    services, context, task = providers
    with ThreadPoolExecutor(max_workers=4) as workers:
        receipts = list(
            workers.map(
                lambda _: services.create(context, task.task_id, "Same case", "same-key"), range(4)
            )
        )
    assert all(receipt == receipts[0] for receipt in receipts)
    with pytest.raises(MockConflictError):
        services.create(context, task.task_id, "Changed case", "same-key")
    with services.store.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM mock_actions").fetchone()[0] == 1


@pytest.mark.parametrize("action", ["ticket", "campaign"])
def test_uncertain_committed_write_can_be_inspected_without_duplication(providers, action):
    services, context, task = providers
    if action == "ticket":

        def call():
            return services.create(context, task.task_id, "Case", "uncertain")

        operation, name = "ticket_after_write", "create_support_ticket"
    else:
        digest = prepare_campaign(services, context, task)

        def call():
            return services.send(context, task.task_id, digest, "uncertain")

        operation, name = "campaign_after_write", "send_campaign"
    services.inject_failure(context, FailureControl(operation=operation))
    with pytest.raises(MockTimeout):
        call()
    stored = services.lookup(context, name, "uncertain")
    assert stored is not None and call() == stored
    with services.store.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM mock_actions").fetchone()[0] == 1


def test_consent_revalidation_and_hash_binding_prevent_invalid_sends(providers):
    services, context, task = providers
    digest = prepare_campaign(services, context, task)
    services.set_consent(context, "customer-001", False)
    with pytest.raises(MockConflictError):
        services.send(context, task.task_id, digest, "consent-check")
    assert services.lookup(context, "send_campaign", "consent-check") is None
    with pytest.raises(KeyError):
        services.send(context, task.task_id, "a" * 64, "wrong-hash")


def test_second_merchant_cannot_read_or_mutate_first_merchant_actions(providers):
    services, context, task = providers
    ticket = services.create(context, task.task_id, "Case", "private")
    other = demo_context("merchant_other").with_updates(scopes=context.scopes)
    with pytest.raises(KeyError):
        services.status(other, ticket.external_reference)
    with pytest.raises(KeyError):
        services.create(other, task.task_id, "Foreign task", "foreign")
    services.set_consent(context, "customer-001", False)
    assert services.customers(other).customers[0].marketing_consent is True
    with pytest.raises(AccessDenied):
        services.customers(demo_context("merchant_other"))
    with pytest.raises(AccessDenied):
        services.report(MERCHANTS["merchant_demo"])


def test_clock_and_failure_scripts_survive_restart_and_reset_is_scoped(providers):
    services, context, task = providers
    before = services.report(context)
    other = demo_context("merchant_other")
    services.advance(other, 60)
    services.inject_failure(context, FailureControl(operation="get_settlement_report", count=2))
    restarted = MockServices(
        SQLiteMockStore(services.store.path), services.tasks, controls_enabled=True
    )
    for _ in range(2):
        with pytest.raises(MockTimeout):
            restarted.report(context)
    assert restarted.report(context) == before
    assert services.fresh_credits(context, task.task_id, "credit-001") == []
    services.advance(context, 86400)
    fresh = services.fresh_credits(context, task.task_id, "credit-001")
    assert len(fresh) == 1 and fresh[0].amount_paise == 16680
    assert fresh[0].captured_at > DEMO_START
    assert services.clock(context) == DEMO_START + timedelta(days=1)
    services.create(context, task.task_id, "Remove on reset", "reset-me")
    services.reset(context)
    assert services.report(context) == before
    assert services.clock(other) == DEMO_START + timedelta(seconds=60)
    assert services.tasks.get_task(context, task.task_id) == task
    assert services.lookup(context, "create_support_ticket", "reset-me") is None


def test_registry_exposes_typed_mock_tools_and_preserves_approval_gate(providers):
    services, context, task = providers
    registry = ToolRegistry()
    register_mock_tools(registry, services)
    assert len(registry.execute("get_transactions", context, {}).records) == 200
    assert registry.execute("get_settlement_report", context, {"task_id": task.task_id})
    with pytest.raises(AccessDenied):
        registry.execute(
            "create_support_ticket",
            context,
            {
                "task_id": task.task_id,
                "summary": "Needs approval",
            },
        )
    assert services.lookup(context, "create_support_ticket", "blocked") is None
    assert all(
        tool.metadata.name != "send_campaign"
        for tool in registry.discover(demo_context("merchant_other"), intent=Intent.WIN_BACK)
    )


def test_demo_controls_are_disabled_without_affecting_read_services(providers):
    services, context, _ = providers
    disabled = MockServices(services.store, services.tasks, controls_enabled=False)
    assert disabled.report(context)
    for call in [
        lambda: disabled.reset(context),
        lambda: disabled.advance(context, 60),
        lambda: disabled.inject_failure(context, FailureControl(operation="get_settlement_report")),
        lambda: disabled.set_consent(context, "customer-001", False),
    ]:
        with pytest.raises(AccessDenied):
            call()


def test_registry_typed_reads_use_stored_mock_state(providers):
    services, context, task = providers
    registry = ToolRegistry()
    register_mock_tools(registry, services)
    assert len(registry.execute("get_refunds_and_chargebacks", context, {}).records) == 4
    assert len(registry.execute("get_customers_and_orders", context, {}).customers) == 200
    ticket = services.create(context, task.task_id, "Independent read", "registry-ticket")
    assert (
        registry.execute(
            "get_ticket_status", context, {"reference": ticket.external_reference}
        ).status
        == "open"
    )
    digest = prepare_campaign(services, context, task)
    campaign = services.send(context, task.task_id, digest, "registry-campaign")
    result = registry.execute(
        "get_campaign_delivery_status", context, {"reference": campaign.external_reference}
    )
    assert result.delivered == 118 and result.failed == 2
    assert result.verified
    with services.store.transaction() as db:
        db.execute(
            "UPDATE mock_actions SET result = ? WHERE reference = ?",
            (json.dumps({"delivered": 117, "failed": 2}), campaign.external_reference),
        )
    assert not registry.execute(
        "get_campaign_delivery_status", context, {"reference": campaign.external_reference}
    ).verified
    tools = registry.discover(context, intent=Intent.HANDOFF)
    assert {tool.metadata.name for tool in tools} == {"get_ticket_status", "create_support_ticket"}
    assert all(tool.input_schema and tool.output_schema for tool in tools)


def test_demo_api_reports_failures_and_rejects_disabled_controls(tmp_path):
    settings = Settings(_env_file=None, database_path=str(tmp_path / "api.sqlite3"))
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/demo/settlement").status_code == 200
        assert len(client.get("/api/v1/demo/customers").json()["customers"]) == 200
        assert (
            client.post(
                "/api/v1/demo/failures", json={"operation": "get_settlement_report"}
            ).status_code
            == 200
        )
        assert client.get("/api/v1/demo/settlement").status_code == 503
        assert client.get("/api/v1/demo/settlement").status_code == 200
        assert client.post("/api/v1/demo/clock/advance", json={"seconds": 86400}).status_code == 200
        assert client.post("/api/v1/demo/clock/advance", json={"seconds": True}).status_code == 422
        assert (
            client.post("/api/v1/demo/reset")
            .json()["current_time"]
            .startswith("2026-11-14T04:00:00")
        )
    with TestClient(
        create_app(settings.model_copy(update={"demo_controls_enabled": False}))
    ) as client:
        assert client.post("/api/v1/demo/reset").status_code == 403
        assert client.post("/api/v1/demo/clock/advance", json={"seconds": 60}).status_code == 403
        assert (
            client.post(
                "/api/v1/demo/failures", json={"operation": "get_settlement_report"}
            ).status_code
            == 403
        )


def test_seed_cli_and_clock_persist_across_processes(tmp_path):
    env = {
        **os.environ,
        "BIZMATE_DATABASE_PATH": str(tmp_path / "cli.sqlite3"),
        "BIZMATE_DEMO_CONTROLS_ENABLED": "true",
    }

    def run(command):
        result = subprocess.run(
            [sys.executable, "backend/scripts/demo_data.py", command],
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.loads(result.stdout)

    assert run("seed")["current_time"] == DEMO_START.isoformat()
    assert run("advance")["current_time"] == (DEMO_START + timedelta(days=1)).isoformat()
    assert run("seed")["current_time"] == (DEMO_START + timedelta(days=1)).isoformat()
    assert run("reset")["current_time"] == DEMO_START.isoformat()


@pytest.mark.parametrize("action", ["create_support_ticket", "send_campaign"])
@pytest.mark.parametrize("timeout", [False, True])
def test_default_app_runs_approved_mock_adapters_and_replays_safely(providers, action, timeout):
    services, context, task = providers
    intent = Intent.SETTLEMENT if action == "create_support_ticket" else Intent.WIN_BACK
    task = services.tasks.save(
        context,
        transition_task(task.with_updates(intent=intent), TaskStatus.PLANNING, "Prepare action"),
    )
    task = services.tasks.save(context, transition_task(task, TaskStatus.READY, "Review action"))
    inputs = {"task_id": task.task_id, "summary": "  Telugu original message\n"}
    if action == "send_campaign":
        inputs = {
            "task_id": task.task_id,
            "message": "An approved synthetic offer",
            "recipient_ids": [c.customer_id for c in services.customers(context).customers[:120]],
            "cost_paise": 24000,
        }
    settings = Settings(_env_file=None, database_path=str(services.store.path))
    with TestClient(create_app(settings)) as client:
        root = f"/api/v1/tasks/{task.task_id}"
        response = client.post(root + "/approvals", json={"action": action, "inputs": inputs})
        assert response.status_code == 201, response.text
        approval = response.json()
        endpoint = root + "/approvals/" + approval["approval_id"]
        assert approval["approved_inputs"] == inputs
        assert client.post(endpoint + "/execute", json={"inputs": inputs}).status_code == 403
        assert (
            client.post(
                endpoint, json={"decision": "approve", "input_hash": approval["input_hash"]}
            ).status_code
            == 200
        )
        changed = {
            **inputs,
            "summary" if action == "create_support_ticket" else "message": "Edited",
        }
        assert client.post(endpoint + "/execute", json={"inputs": changed}).status_code == 409
        if timeout:
            operation = (
                "ticket_after_write"
                if action == "create_support_ticket"
                else "campaign_after_write"
            )
            services.inject_failure(context, FailureControl(operation=operation))
        response = client.post(endpoint + "/execute", json={"inputs": inputs})
        assert response.status_code == (409 if timeout else 200), response.text
        if timeout:
            saved = client.get(root).json()
            key = saved["tool_executions"][0]["execution_id"]
            assert services.lookup(context, action, key) is not None
            assert saved["status"] == "WAITING_EXTERNAL" and not saved["receipts"]
        else:
            receipt = response.json()
            assert services.lookup(context, action, receipt["idempotency_key"]) is not None
            result = client.post(root + "/receipts/" + receipt["receipt_id"] + "/verify")
            assert result.status_code == 200 and result.json()["verified"], result.text
            assert client.get(root).json()["status"] == "VERIFYING"
    with TestClient(create_app(settings)) as restarted:
        replay = restarted.post(endpoint + "/execute", json={"inputs": inputs})
        assert replay.status_code == (409 if timeout else 200)
        if not timeout:
            assert replay.json() == receipt
    with services.store.transaction() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM mock_actions WHERE merchant_id = ? AND action = ?",
                (context.merchant_id, action),
            ).fetchone()[0]
            == 1
        )


def test_engine_rejects_action_inputs_for_another_task(providers):
    from bizmate.tools.policy import ActionConflict, ApprovalEngine

    services, context, task = providers
    task = services.tasks.save(
        context,
        transition_task(
            task.with_updates(intent=Intent.SETTLEMENT), TaskStatus.PLANNING, "Prepare action"
        ),
    )
    services.tasks.save(context, transition_task(task, TaskStatus.READY, "Review action"))
    registry = ToolRegistry()
    register_mock_tools(registry, services)
    with pytest.raises(ActionConflict, match="this task"):
        ApprovalEngine(services.tasks, registry).request(
            context,
            task.task_id,
            "create_support_ticket",
            {"task_id": "other-task", "summary": "Wrong task"},
        )
