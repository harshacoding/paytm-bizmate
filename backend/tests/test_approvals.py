import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from bizmate.config import Settings
from bizmate.domain.errors import AccessDenied
from bizmate.domain.models import (
    ActionResult,
    Intent,
    Model,
    Scope,
    Task,
    TaskStatus,
    ToolExecution,
    VerificationResult,
)
from bizmate.domain.types import Identifier, MessageText
from bizmate.main import create_app
from bizmate.persistence.repository import MemoryTaskRepository, TaskConflictError
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import demo_context
from bizmate.tools.policy import ActionConflict, ActionNotFound, ApprovalEngine, input_hash
from bizmate.tools.registry import PreconditionFailed, ToolMetadata, ToolRegistry, VerificationSpec


class WriteInputs(Model):
    summary: MessageText


class ReadInputs(Model):
    reference: Identifier


class TicketMock:
    def __init__(self, path):
        self.path = path
        self.calls = 0
        self.reads = 0
        self.ready = True
        self.fail = None
        self.wrong = None
        with sqlite3.connect(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS tickets (key TEXT PRIMARY KEY, merchant TEXT, "
                "task TEXT, reference TEXT, summary TEXT)"
            )

    def create(self, context, inputs, *, idempotency_key):
        self.calls += 1
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT OR IGNORE INTO tickets VALUES (?, ?, ?, ?, ?)",
                (idempotency_key, context.merchant_id, "t1", "ticket-1", inputs.summary),
            )
        if self.fail == "timeout":
            raise TimeoutError("sensitive provider response")
        if self.fail == "invalid":
            return {"unverified_success": True}
        return ActionResult(external_reference="ticket-1")

    def read(self, context, inputs):
        self.reads += 1
        if self.fail == "read_timeout":
            raise TimeoutError("sensitive read response")
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT task, reference FROM tickets WHERE merchant = ? AND reference = ?",
                (context.merchant_id, inputs.reference),
            ).fetchone()
        return VerificationResult(
            merchant_id="merchant_other" if self.wrong == "merchant" else context.merchant_id,
            task_id="other" if self.wrong == "task" else "t1",
            external_reference="wrong" if self.wrong == "reference" else inputs.reference,
            verified=row is not None,
            evidence_reference="stored-ticket-read",
        )

    def registry(self):
        registry = ToolRegistry()
        registry.register(
            ToolMetadata(
                name="get_ticket_status",
                description="Read the separately stored ticket",
                category="support",
                risk="read",
                intents=[Intent.SETTLEMENT],
                required_scopes=[Scope.TASKS_READ],
            ),
            ReadInputs,
            self.read,
            output_schema=VerificationResult,
        )
        registry.register(
            ToolMetadata(
                name="create_support_ticket",
                description="Create a synthetic ticket",
                category="support",
                risk="side_effect",
                intents=[Intent.SETTLEMENT],
                required_scopes=[Scope.TICKETS_WRITE],
                approval_required=True,
                idempotency="key_required",
                preconditions=["ready"],
                verification=VerificationSpec(
                    tool_name="get_ticket_status", description="Read ticket"
                ),
            ),
            WriteInputs,
            self.create,
            output_schema=ActionResult,
            preconditions={"ready": lambda context, inputs: self.ready},
        )
        return registry


@pytest.fixture(params=["memory", "sqlite"])
def setup(request, tmp_path):
    repo = (
        MemoryTaskRepository()
        if request.param == "memory"
        else SQLiteTaskRepository(tmp_path / "tasks.sqlite3")
    )
    context = demo_context("merchant_demo")
    repo.save(
        context,
        Task(
            task_id="t1",
            merchant_id=context.merchant_id,
            goal="Investigate settlement",
            original_request="Original",
            next_action="Prepare action",
            intent=Intent.SETTLEMENT,
            status=TaskStatus.READY,
        ),
    )
    service = TicketMock(tmp_path / "external.sqlite3")
    return repo, context, service, ApprovalEngine(repo, service.registry())


def approved(setup):
    repo, ctx, service, engine = setup
    approval = engine.request(ctx, "t1", "create_support_ticket", {"summary": "  తెలుగు Hindi\n"})
    return engine.decide(ctx, "t1", approval.approval_id, "approve", approval.input_hash)


def execute(setup, approval):
    return setup[3].execute(setup[1], "t1", approval.approval_id, approval.approved_inputs)


def test_exact_approval_receipt_then_independent_verification(setup):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    assert approval.approver == ctx.actor_id
    assert any(ctx.actor_id in event.message for event in repo.get_task(ctx, "t1").events)
    assert approval.approved_inputs == {"summary": "  తెలుగు Hindi\n"}
    assert approval.input_hash == input_hash(
        ctx.merchant_id, "t1", approval.action, approval.approved_inputs
    )
    receipt = execute(setup, approval)
    assert service.calls == 1 and service.reads == 0
    task = repo.get_task(ctx, "t1")
    assert task.status == TaskStatus.VERIFYING and not task.verifications
    assert receipt.input_hash == approval.input_hash
    assert execute(setup, approval) == receipt
    assert service.calls == 1
    result = engine.verify(ctx, "t1", receipt.receipt_id)
    assert result.verified and service.reads == 1
    assert repo.get_task(ctx, "t1").status == TaskStatus.VERIFYING


def test_pending_cancelled_and_changed_inputs_cannot_execute(setup):
    repo, ctx, service, engine = setup
    approval = engine.request(ctx, "t1", "create_support_ticket", {"summary": "Original"})
    with pytest.raises(AccessDenied):
        execute(setup, approval)
    with pytest.raises(ActionConflict):
        engine.decide(ctx, "t1", approval.approval_id, "approve", "a" * 64)
    decided = engine.decide(ctx, "t1", approval.approval_id, "approve", approval.input_hash)
    with pytest.raises(ActionConflict):
        engine.execute(ctx, "t1", approval.approval_id, {"summary": "Edited"})
    engine.decide(ctx, "t1", decided.approval_id, "cancel", decided.input_hash)
    with pytest.raises(AccessDenied):
        execute(setup, decided)
    with pytest.raises(ActionConflict):
        engine.decide(ctx, "t1", decided.approval_id, "approve", decided.input_hash)
    assert service.calls == 0


def test_missing_wrong_merchant_actor_and_revoked_scopes(setup):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    with pytest.raises(ActionNotFound):
        engine.execute(ctx, "t1", "missing", approval.approved_inputs)
    with pytest.raises(ActionNotFound):
        engine.execute(
            demo_context("merchant_other"), "t1", approval.approval_id, approval.approved_inputs
        )
    with pytest.raises(AccessDenied):
        engine.execute(
            ctx.with_updates(actor_id="another-actor"),
            "t1",
            approval.approval_id,
            approval.approved_inputs,
        )
    for scope in [Scope.TASKS_WRITE, Scope.TASKS_APPROVE, Scope.TICKETS_WRITE]:
        with pytest.raises(AccessDenied):
            engine.execute(
                ctx.with_updates(scopes=ctx.scopes - {scope}),
                "t1",
                approval.approval_id,
                approval.approved_inputs,
            )
    assert service.calls == 0


def test_preconditions_rechecked_after_approval(setup):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    service.ready = False
    with pytest.raises(PreconditionFailed):
        execute(setup, approval)
    assert service.calls == 0 and not repo.get_task(ctx, "t1").tool_executions


@pytest.mark.parametrize("failure", ["timeout", "invalid"])
def test_write_may_have_happened_and_is_never_retried(setup, failure):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    service.fail = failure
    with pytest.raises(ActionConflict):
        execute(setup, approval)
    task = repo.get_task(ctx, "t1")
    assert task.status == TaskStatus.WAITING_EXTERNAL
    assert task.tool_executions[0].outcome == "uncertain" and not task.receipts
    with pytest.raises(ActionConflict, match="unresolved"):
        engine.request(ctx, "t1", approval.action, approval.approved_inputs)
    # Rebuild the engine and adapter, not just the request, before trying again.
    reopened = (
        SQLiteTaskRepository(repo.database_path) if isinstance(repo, SQLiteTaskRepository) else repo
    )
    next_service = TicketMock(service.path)
    with pytest.raises(ActionConflict):
        ApprovalEngine(reopened, next_service.registry()).execute(
            ctx, "t1", approval.approval_id, approval.approved_inputs
        )
    assert service.calls == 1 and next_service.calls == 0
    with sqlite3.connect(service.path) as db:
        assert db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 1


@pytest.mark.parametrize("failure", ["read_timeout", "reference", "task", "merchant", "deleted"])
def test_verification_failure_is_visible_and_does_not_complete(setup, failure):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    receipt = execute(setup, approval)
    if failure == "read_timeout":
        service.fail = failure
    elif failure == "deleted":
        with sqlite3.connect(service.path) as db:
            db.execute("DELETE FROM tickets")
    else:
        service.wrong = failure
    assert not engine.verify(ctx, "t1", receipt.receipt_id).verified
    task = repo.get_task(ctx, "t1")
    assert task.status == TaskStatus.VERIFYING
    assert task.events[-1].kind == "verification_failed"
    assert "failed" in task.next_action.lower()
    assert service.calls == 1


def test_receipts_and_approval_snapshots_are_immutable(setup):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    task = repo.get_task(ctx, "t1")
    with pytest.raises(ValueError, match="immutable"):
        repo.save(
            ctx,
            task.with_updates(
                approvals=(approval.with_updates(approved_inputs={"summary": "Edited"}),)
            ),
        )
    receipt = execute(setup, approval)
    task = repo.get_task(ctx, "t1")
    for field in ["receipts", "tool_executions"]:
        with pytest.raises(ValueError, match="append-only"):
            repo.save(ctx, task.with_updates(**{field: ()}))
    engine.verify(ctx, "t1", receipt.receipt_id)
    task = repo.get_task(ctx, "t1")
    with pytest.raises(ValueError, match="append-only"):
        repo.save(ctx, task.with_updates(verifications=()))
    with pytest.raises(ActionConflict):
        engine.decide(ctx, "t1", approval.approval_id, "cancel", approval.input_hash)


def test_sqlite_restart_preserves_approval_receipt_and_verification(setup):
    repo, ctx, service, engine = setup
    if not isinstance(repo, SQLiteTaskRepository):
        pytest.skip("restart requires disk storage")
    approval = approved(setup)
    engine = ApprovalEngine(SQLiteTaskRepository(repo.database_path), service.registry())
    receipt = engine.execute(ctx, "t1", approval.approval_id, approval.approved_inputs)
    another_service = TicketMock(service.path)
    restarted = ApprovalEngine(SQLiteTaskRepository(repo.database_path), another_service.registry())
    assert restarted.execute(ctx, "t1", approval.approval_id, approval.approved_inputs) == receipt
    assert another_service.calls == 0
    verification = restarted.verify(ctx, "t1", receipt.receipt_id)
    restored = SQLiteTaskRepository(repo.database_path).get_task(ctx, "t1")
    assert restored.verifications == (verification,)
    assert restored.approvals == (approval,)


def test_concurrent_execution_claim_is_atomic(setup, monkeypatch):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    barrier = Barrier(2)
    original_get = repo.get_task

    def simultaneous_read(*args):
        task = original_get(*args)
        barrier.wait(timeout=5)
        return task

    monkeypatch.setattr(repo, "get_task", simultaneous_read)

    def run():
        try:
            return execute(setup, approval)
        except TaskConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert sum(r is not None for r in results) == 1
    assert service.calls == 1


def test_approval_http_contract_and_validation(setup, tmp_path):
    repo, ctx, service, engine = setup
    app = create_app(
        Settings(_env_file=None, database_path=str(tmp_path / "chat.sqlite3")),
        repo=repo,
        tools=service.registry(),
    )
    with TestClient(app) as client:
        root = "/api/v1/tasks/t1"
        assert (
            client.post(
                root + "/approvals",
                json={
                    "action": "create_support_ticket",
                    "inputs": {"summary": 123},
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                root + "/approvals",
                json={
                    "action": "create_support_ticket",
                    "inputs": {"summary": "ok"},
                    "approved": True,
                },
            ).status_code
            == 422
        )
        response = client.post(
            root + "/approvals",
            json={
                "action": "create_support_ticket",
                "inputs": {"summary": "Original"},
            },
        )
        assert response.status_code == 201
        approval = response.json()
        endpoint = root + "/approvals/" + approval["approval_id"]
        assert (
            client.post(endpoint, json={"decision": "approve", "input_hash": "a" * 64}).status_code
            == 409
        )
        decision = client.post(
            endpoint,
            json={
                "decision": "approve",
                "input_hash": approval["input_hash"],
            },
        )
        assert decision.status_code == 200
        assert (
            client.post(
                endpoint + "/execute",
                json={
                    "inputs": {"summary": "Edited"},
                },
            ).status_code
            == 409
        )
        receipt = client.post(
            endpoint + "/execute",
            json={
                "inputs": {"summary": "Original"},
            },
        )
        assert receipt.status_code == 200
        result = client.post(root + "/receipts/" + receipt.json()["receipt_id"] + "/verify")
        assert result.status_code == 200 and result.json()["verified"]
        assert client.get(root).json()["status"] != "COMPLETED"


def test_approval_decision_replay_and_new_inputs_need_new_approval(setup):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    assert (
        engine.decide(ctx, "t1", approval.approval_id, "approve", approval.input_hash) == approval
    )
    engine.decide(ctx, "t1", approval.approval_id, "cancel", approval.input_hash)
    task = repo.get_task(ctx, "t1")
    repo.save(ctx, task.with_updates(status=TaskStatus.READY))
    fresh = engine.request(ctx, "t1", approval.action, {"summary": "Edited"})
    assert fresh.approval_id != approval.approval_id
    assert fresh.input_hash != approval.input_hash
    assert fresh.decision == "pending"
    with pytest.raises(AccessDenied):
        execute(setup, fresh)
    assert service.calls == 0


def test_receipt_alone_and_latest_failed_verification_cannot_complete(setup):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    receipt = execute(setup, approval)
    with pytest.raises(ValidationError):
        repo.get_task(ctx, "t1").with_updates(status=TaskStatus.COMPLETED)
    engine.verify(ctx, "t1", receipt.receipt_id)
    assert repo.get_task(ctx, "t1").with_updates(intent=Intent.HANDOFF, status=TaskStatus.COMPLETED)
    task = repo.get_task(ctx, "t1")
    unresolved = ToolExecution(
        execution_id="another-claim",
        task_id="t1",
        merchant_id=ctx.merchant_id,
        tool_name=approval.action,
        input_hash=approval.input_hash,
        outcome="uncertain",
    )
    with pytest.raises(ValidationError, match="uncertain"):
        task.with_updates(
            status=TaskStatus.COMPLETED, tool_executions=(*task.tool_executions, unresolved)
        )
    service.fail = "read_timeout"
    engine.verify(ctx, "t1", receipt.receipt_id)
    with pytest.raises(ValidationError):
        repo.get_task(ctx, "t1").with_updates(status=TaskStatus.COMPLETED)


def test_a_concurrent_save_after_the_write_cannot_cause_a_duplicate(setup, monkeypatch):
    repo, ctx, service, engine = setup
    approval = approved(setup)
    original = service.create

    def write_and_change_task(*args, **kwargs):
        result = original(*args, **kwargs)
        task = repo.get_task(ctx, "t1")
        repo.save(ctx, task.with_updates(next_action="A concurrent timeline update"))
        return result

    monkeypatch.setattr(service, "create", write_and_change_task)
    engine.registry = service.registry()
    with pytest.raises(TaskConflictError):
        execute(setup, approval)
    restarted = ApprovalEngine(repo, service.registry())
    with pytest.raises(ActionConflict, match="unresolved"):
        restarted.execute(ctx, "t1", approval.approval_id, approval.approved_inputs)
    assert service.calls == 1
    assert not repo.get_task(ctx, "t1").receipts


def test_hash_is_order_independent_and_bound_to_action_task_and_merchant():
    digest = input_hash("m", "t", "send", {"b": 2, "a": 1})
    assert digest == input_hash("m", "t", "send", {"a": 1, "b": 2})
    for merchant, task, action, inputs in [
        ("other", "t", "send", {"a": 1, "b": 2}),
        ("m", "other", "send", {"a": 1, "b": 2}),
        ("m", "t", "other", {"a": 1, "b": 2}),
        ("m", "t", "send", {"a": True, "b": 2}),
    ]:
        assert digest != input_hash(merchant, task, action, inputs)
