from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from bizmate.config import Settings
from bizmate.domain.models import SettlementResolution, TaskStatus, now
from bizmate.main import create_app
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import demo_context
from bizmate.services.mock_models import FailureControl, PaymentRecord
from bizmate.services.mock_store import SQLiteMockStore
from bizmate.services.mocks import MockServices
from bizmate.services.scheduler import run_due_tasks
from bizmate.tools.mock_tools import register_mock_tools
from bizmate.tools.policy import ActionConflict, ActionNotFound
from bizmate.tools.registry import ToolRegistry
from bizmate.tools.settlement_tools import register_settlement_tools
from bizmate.workflows.investigation import (
    InvestigationRequest,
    SettlementInvestigation,
    state_of,
    with_state,
)


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(Settings(_env_file=None, database_path=str(tmp_path / "app.sqlite3")))
    ) as client:
        yield client


def start(client, key="test-1"):
    r = client.post("/api/v1/settlements/investigations", json={"client_request_id": key})
    assert r.status_code == 201, r.text
    return r.json()


def approve(client, view):
    task = view["task"]
    approval = task["approvals"][0]
    r = client.post(
        f"/api/v1/tasks/{task['task_id']}/approvals/{approval['approval_id']}",
        json={"decision": "approve", "input_hash": approval["input_hash"]},
    )
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/settlements/investigations/{task['task_id']}/resume")
    assert r.status_code == 200, r.text
    return r.json()


def test_hero_flow(client):
    view = start(client)
    assert view["state"]["proof"]["residual"]["amount_paise"] == 16680
    assert view["task"]["status"] == "AWAITING_APPROVAL"
    waiting = approve(client, view)
    assert waiting["task"]["status"] == "WAITING_EXTERNAL"
    assert waiting["task"]["verifications"][-1]["verified"]
    assert len(waiting["task"]["receipts"]) == 1
    r = client.post("/api/v1/demo/clock/advance", json={"seconds": 86400})
    assert r.status_code == 200, r.text
    result = client.get("/api/v1/settlements/investigations/" + view["task"]["task_id"]).json()
    assert result["task"]["status"] == "COMPLETED", result
    assert result["resolution"]["amount_paise"] == 16680
    assert result["task"]["next_run_at"] is None
    assert client.post("/api/v1/settlements/run-due").json() == []


def make_workflow(path):
    repo = SQLiteTaskRepository(path)
    services = MockServices(SQLiteMockStore(path), repo, controls_enabled=True)
    registry = ToolRegistry()
    register_mock_tools(registry, services)
    register_settlement_tools(registry, services)
    return SettlementInvestigation(repo, services, registry)


@pytest.fixture
def workflow(tmp_path):
    return make_workflow(tmp_path / "workflow.sqlite3")


def begin(workflow, key="investigation-1"):
    return workflow.start(
        demo_context("merchant_demo"), InvestigationRequest(client_request_id=key)
    )


def waiting(workflow):
    ctx = demo_context("merchant_demo")
    task = begin(workflow)
    approval = task.approvals[0]
    workflow.approvals.decide(
        ctx, task.task_id, approval.approval_id, "approve", approval.input_hash
    )
    return workflow.resume(ctx, task.task_id)


def action_count(workflow):
    with workflow.services.store.transaction() as db:
        return db.execute("SELECT COUNT(*) FROM mock_actions").fetchone()[0]


def alter(workflow, reference, **changes):
    ctx = demo_context("merchant_demo")
    record = next(
        r
        for r in workflow.services.store.records(ctx.merchant_id, "payment")
        if r["reference"] == reference
    )
    changed = PaymentRecord.model_validate(record).with_updates(**changes)
    with workflow.services.store.transaction() as db:
        workflow.services.store.put(
            db, ctx.merchant_id, "payment", reference, changed.model_dump(mode="json")
        )


def delete(workflow, reference):
    with workflow.services.store.transaction() as db:
        db.execute(
            "DELETE FROM mock_records WHERE merchant_id = ? AND kind = ? AND reference = ?",
            ("merchant_demo", "payment", reference),
        )


@pytest.mark.parametrize("timeouts", [1, 3, 8])
def test_report_recovery_is_bounded_and_visible(workflow, timeouts):
    ctx = demo_context("merchant_demo")
    workflow.services.inject_failure(
        ctx, FailureControl(operation="get_settlement_report", count=timeouts)
    )
    task = begin(workflow)
    assert task.status == TaskStatus.AWAITING_APPROVAL
    assert state_of(task).proof.residual.amount_paise == 16680
    assert state_of(task).report_attempts == min(timeouts + 1, 3)
    assert len([e for e in task.events if e.kind == "report_timeout"]) == min(timeouts, 3)
    assert any(e.kind == "ledger_fallback" for e in task.events) == (timeouts >= 3)
    assert action_count(workflow) == 0


def test_unavailable_fallback_or_missing_records_never_make_a_case(workflow):
    ctx = demo_context("merchant_demo")
    workflow.services.inject_failure(
        ctx, FailureControl(operation="get_settlement_report", count=3)
    )
    workflow.services.inject_failure(ctx, FailureControl(operation="get_transactions", count=1))
    task = begin(workflow)
    assert task.status == TaskStatus.ESCALATED and not task.approvals
    delete(workflow, "commission-001")
    another = begin(workflow, "missing-record")
    assert another.status == TaskStatus.ESCALATED and not another.approvals
    assert state_of(another).proof.residual.amount_paise is None


def test_repeated_start_scan_resume_and_cancel_are_safe(workflow):
    ctx = demo_context("merchant_demo")
    task = begin(workflow)
    assert begin(workflow) == task
    assert [t.task_id for t in workflow.scan(ctx)] == [task.task_id]
    assert action_count(workflow) == 0
    with pytest.raises(ActionConflict):
        workflow.start(
            ctx, InvestigationRequest(client_request_id="investigation-1", message="Changed")
        )
    approval = task.approvals[0]
    workflow.approvals.decide(
        ctx, task.task_id, approval.approval_id, "cancel", approval.input_hash
    )
    assert workflow.resume(ctx, task.task_id).status == TaskStatus.PLANNING
    assert action_count(workflow) == 0


def test_proactive_scan_is_deduplicated(workflow):
    ctx = demo_context("merchant_demo")
    first = workflow.scan(ctx)
    assert len(first) == 1 and first[0].status == TaskStatus.AWAITING_APPROVAL
    assert workflow.scan(ctx) == first
    assert len(workflow.repo.list_tasks(ctx)) == 1


def test_ticket_timeout_is_not_replayed(workflow):
    ctx = demo_context("merchant_demo")
    task = begin(workflow)
    approval = task.approvals[0]
    workflow.approvals.decide(
        ctx, task.task_id, approval.approval_id, "approve", approval.input_hash
    )
    workflow.services.inject_failure(ctx, FailureControl(operation="ticket_after_write"))
    for _ in range(2):
        with pytest.raises(ActionConflict):
            workflow.resume(ctx, task.task_id)
    saved = workflow.get(ctx, task.task_id)
    assert saved.status == TaskStatus.WAITING_EXTERNAL and saved.next_run_at is None
    assert action_count(workflow) == 1
    assert run_due_tasks(workflow, ctx) == []


def test_failed_ticket_verification_can_retry_the_read_only(workflow):
    ctx = demo_context("merchant_demo")
    workflow.services.inject_failure(ctx, FailureControl(operation="get_ticket_status"))
    task = waiting(workflow)
    assert task.status == TaskStatus.VERIFYING and not task.verifications[-1].verified
    assert task.next_run_at is None
    resumed = workflow.resume(ctx, task.task_id)
    assert resumed.status == TaskStatus.WAITING_EXTERNAL
    assert resumed.verifications[-1].verified and action_count(workflow) == 1
    with pytest.raises(ValidationError):
        resumed.with_updates(
            status=TaskStatus.COMPLETED,
            next_run_at=None,
            plan=tuple(p.with_updates(status="done") for p in resumed.plan),
        )


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("missing", "WAITING_EXTERNAL"),
        ("stale", "WAITING_EXTERNAL"),
        ("wrong_settlement", "WAITING_EXTERNAL"),
        ("wrong_merchant", "WAITING_EXTERNAL"),
        ("wrong_amount", "ESCALATED"),
        ("changed_baseline", "ESCALATED"),
        ("new_deduction", "ESCALATED"),
        ("duplicate_credit", "ESCALATED"),
    ],
)
def test_only_fresh_matching_consistent_evidence_closes(workflow, mutation, expected):
    ctx = demo_context("merchant_demo")
    task = waiting(workflow)
    state = state_of(task)
    if mutation in {"missing", "wrong_merchant"}:
        delete(workflow, "credit-held-001")
    elif mutation == "stale":
        alter(workflow, "credit-held-001", available_at=state.proof.captured_at)
    elif mutation == "wrong_settlement":
        alter(workflow, "credit-held-001", settlement_reference="other-settlement")
    elif mutation == "wrong_amount":
        alter(workflow, "credit-held-001", amount_paise=16679)
    elif mutation == "changed_baseline":
        alter(workflow, "commission-001", amount_paise=25000)
    if mutation in {"new_deduction", "duplicate_credit"}:
        record = PaymentRecord(
            reference="extra-record",
            kind="refund" if mutation == "new_deduction" else "credit",
            amount_paise=100 if mutation == "new_deduction" else 16680,
            available_at=state.proof.captured_at + timedelta(days=1),
        )
        with workflow.services.store.transaction() as db:
            workflow.services.store.put(
                db, ctx.merchant_id, "payment", record.reference, record.model_dump(mode="json")
            )
    workflow.services.advance(ctx, 86400)
    result = run_due_tasks(workflow, ctx)
    assert result[0].status.value == expected
    assert "settlement_resolution" not in result[0].workflow_data
    assert action_count(workflow) == 1


def test_follow_up_read_timeouts_and_missing_credit_are_bounded(workflow):
    ctx = demo_context("merchant_demo")
    task = waiting(workflow)
    delete(workflow, "credit-held-001")
    workflow.services.inject_failure(ctx, FailureControl(operation="fresh_credits"))
    for attempt in range(3):
        workflow.services.advance(ctx, 86400)
        task = run_due_tasks(workflow, ctx)[0]
        assert state_of(task).follow_up_attempts == attempt + 1
    assert task.status == TaskStatus.ESCALATED and task.next_run_at is None
    assert run_due_tasks(workflow, ctx) == []


def test_restart_runs_due_tasks_at_startup(workflow):
    ctx = demo_context("merchant_demo")
    task = waiting(workflow)
    assert run_due_tasks(workflow, ctx) == []
    workflow.services.advance(ctx, 86400)
    settings = Settings(_env_file=None, database_path=str(workflow.repo.database_path))
    with TestClient(create_app(settings)) as restarted:
        saved = restarted.get("/api/v1/settlements/investigations/" + task.task_id).json()
        assert saved["task"]["status"] == "COMPLETED"
        assert saved["resolution"]["source_reference"] == "credit-held-001"
    reopened = make_workflow(workflow.repo.database_path)
    assert run_due_tasks(reopened, ctx) == []
    saved = reopened.get(ctx, task.task_id)
    assert len([e for e in saved.events if e.kind == "settlement_resolved"]) == 1
    assert action_count(reopened) == 1


def test_concurrent_runners_close_only_once(workflow, monkeypatch):
    ctx = demo_context("merchant_demo")
    task = waiting(workflow)
    workflow.services.advance(ctx, 86400)
    barrier = Barrier(2)
    original = workflow.repo.list_tasks

    def simultaneous(context):
        snapshot = original(context)
        barrier.wait(timeout=5)
        return snapshot

    monkeypatch.setattr(workflow.repo, "list_tasks", simultaneous)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run_due_tasks(workflow, ctx), range(2)))
    assert sum(len(r) for r in results) == 1
    assert workflow.get(ctx, task.task_id).status == TaskStatus.COMPLETED
    assert action_count(workflow) == 1


@pytest.mark.parametrize("interruption", ["claimed", "verified"])
def test_restart_after_interruption_recovers_without_duplicate_closure(
    workflow, monkeypatch, interruption
):
    import bizmate.services.scheduler as scheduler

    ctx = demo_context("merchant_demo")
    task = waiting(workflow)
    workflow.services.advance(ctx, 86400)

    def crash(*args):
        raise SystemExit("simulated process interruption")

    with monkeypatch.context() as patch:
        if interruption == "claimed":
            patch.setattr(workflow.services, "follow_up_records", crash)
        else:
            patch.setattr(scheduler, "_complete", crash)
        with pytest.raises(SystemExit):
            run_due_tasks(workflow, ctx)
    saved = workflow.get(ctx, task.task_id)
    if interruption == "claimed":
        assert saved.status == TaskStatus.RUNNING
        saved = with_state(
            saved, state_of(saved).with_updates(claim_until=now() - timedelta(seconds=1))
        )
        workflow.repo.save(ctx, saved)
    else:
        assert saved.status == TaskStatus.VERIFYING
    reopened = make_workflow(workflow.repo.database_path)
    assert run_due_tasks(reopened, ctx)[0].status == TaskStatus.COMPLETED
    assert action_count(reopened) == 1


def test_permissions_ownership_and_resolution_validation(workflow):
    from bizmate.domain.errors import AccessDenied

    ctx = demo_context("merchant_demo")
    task = waiting(workflow)
    with pytest.raises(ActionNotFound):
        workflow.get(demo_context("merchant_other"), task.task_id)
    with pytest.raises(AccessDenied):
        workflow.start(
            demo_context("merchant_other"), InvestigationRequest(client_request_id="other")
        )
    workflow.services.advance(ctx, 86400)
    finished = run_due_tasks(workflow, ctx)[0]
    resolution = SettlementResolution.model_validate(
        finished.workflow_data["settlement_resolution"]
    )
    for changes in [
        {"source_reference": "credit-001"},
        {"amount_paise": 1},
        {"available_at": resolution.baseline_captured_at},
    ]:
        with pytest.raises(ValidationError):
            resolution.with_updates(**changes)


def test_claim_attempt_budget_survives_repeated_interruptions(workflow, monkeypatch):
    ctx = demo_context("merchant_demo")
    task = waiting(workflow)
    workflow.services.advance(ctx, 86400)
    calls = []

    def crash(*args):
        calls.append(True)
        raise SystemExit("interruption")

    monkeypatch.setattr(workflow.services, "follow_up_records", crash)
    for attempt in range(3):
        with pytest.raises(SystemExit):
            run_due_tasks(workflow, ctx)
        saved = workflow.get(ctx, task.task_id)
        assert state_of(saved).follow_up_attempts == attempt + 1
        saved = with_state(
            saved, state_of(saved).with_updates(claim_until=now() - timedelta(seconds=1))
        )
        workflow.repo.save(ctx, saved)
    assert run_due_tasks(workflow, ctx)[0].status == TaskStatus.ESCALATED
    assert len(calls) == 3


def test_active_lease_and_not_due_tasks_are_not_processed(workflow):
    from bizmate.domain.lifecycle import transition_task

    ctx = demo_context("merchant_demo")
    task = waiting(workflow)
    assert run_due_tasks(workflow, ctx) == []
    workflow.services.advance(ctx, 86400)
    state = state_of(task).with_updates(claim_until=now() + timedelta(minutes=1))
    task = workflow.repo.save(
        ctx, transition_task(with_state(task, state), TaskStatus.RUNNING, "Claimed")
    )
    assert run_due_tasks(workflow, ctx) == []
    assert workflow.get(ctx, task.task_id).revision == task.revision


def test_resolution_cannot_be_attached_to_a_different_task(workflow):
    ctx = demo_context("merchant_demo")
    waiting(workflow)
    workflow.services.advance(ctx, 86400)
    finished = run_due_tasks(workflow, ctx)[0]
    for field in ["task_id", "merchant_id"]:
        changed = {**finished.workflow_data["settlement_resolution"], field: "other"}
        with pytest.raises(ValidationError):
            finished.with_updates(
                workflow_data={**finished.workflow_data, "settlement_resolution": changed}
            )
    changed = {**finished.workflow_data["settlement_resolution"], "baseline_credit_references": []}
    with pytest.raises(ValidationError):
        finished.with_updates(
            workflow_data={**finished.workflow_data, "settlement_resolution": changed}
        )
    proof = state_of(finished).proof.with_updates(settlement_reference="other")
    edited = with_state(
        finished.with_updates(status=TaskStatus.VERIFYING),
        state_of(finished).with_updates(proof=proof),
    )
    with pytest.raises(ValueError, match="immutable"):
        workflow.repo.save(ctx, edited)


def test_http_ownership_request_validation_and_scanning(client):
    from bizmate.api.dependencies import current_context

    view = start(client)
    root = "/api/v1/settlements/investigations"
    task_id = view["task"]["task_id"]
    assert (
        client.post(root, json={"client_request_id": "test-1", "message": "Changed"}).status_code
        == 409
    )
    assert (
        client.post(root, json={"client_request_id": "bad", "merchant_id": "other"}).status_code
        == 422
    )
    assert client.post("/api/v1/settlements/scan").json()[0]["task"]["task_id"] == task_id
    client.app.dependency_overrides[current_context] = lambda: demo_context("merchant_other")
    assert client.get(root + "/" + task_id).status_code == 404
    assert client.post(root, json={"client_request_id": "other"}).status_code == 403
    assert client.post(root + "/" + task_id + "/resume").status_code == 404
    client.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "message,language",
    [
        ("Why is my settlement short?", "en"),
        ("నా సెటిల్‌మెంట్ ఎందుకు తక్కువగా ఉంది?", "te"),
        ("मेरा सेटलमेंट कम क्यों आया है?", "hi"),
    ],
)
def test_natural_language_graph_schedules_and_closes_the_same_task(client, message, language):
    response = client.post("/api/v1/tasks", json={"message": message})
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["status"] == "AWAITING_APPROVAL", task
    assert task["workflow_data"]["response_language"] == language
    approval = task["approvals"][-1]
    root = "/api/v1/tasks/" + task["task_id"]
    assert (
        client.post(
            root + "/approvals/" + approval["approval_id"],
            json={"decision": "approve", "input_hash": approval["input_hash"]},
        ).status_code
        == 200
    )
    response = client.post(root + "/resume")
    assert response.status_code == 200, response.text
    waiting = response.json()
    assert waiting["status"] == "WAITING_EXTERNAL", waiting
    assert waiting["schedule_clock"] == "demo" and waiting["next_run_at"]
    assert waiting["checkpoint_id"]
    assert client.post("/api/v1/demo/clock/advance", json={"seconds": 86400}).status_code == 200
    completed = client.get(root).json()
    assert completed["status"] == "COMPLETED", completed
    assert completed["original_request"] == message
    assert completed["workflow_data"]["response_language"] == language
    assert len(completed["receipts"]) == 1
    if language == "te":
        assert any("\u0c00" <= c <= "\u0c7f" for c in completed["next_action"])
    if language == "hi":
        assert any("\u0900" <= c <= "\u097f" for c in completed["next_action"])
