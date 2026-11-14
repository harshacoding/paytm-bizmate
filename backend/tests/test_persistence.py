import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import pytest
from pydantic_core import PydanticSerializationError

from bizmate.config import BACKEND_ROOT, Settings
from bizmate.domain.models import (
    Approval,
    Evidence,
    PlanStep,
    Receipt,
    Task,
    TaskEvent,
    TaskStatus,
    ToolExecution,
    Verification,
)
from bizmate.persistence.repository import MemoryTaskRepository, TaskConflictError
from bizmate.persistence.sqlite import SQLiteTaskRepository


@pytest.fixture
def saved_task(tmp_path):
    path = tmp_path / "nested" / "tasks.sqlite3"
    repo = SQLiteTaskRepository(path)
    task = Task(
        merchant_id="merchant_demo",
        goal="Verify missing credit",
        original_request="Why is my settlement short?",
        status=TaskStatus.WAITING_EXTERNAL,
        next_action="Read fresh settlement evidence",
        next_run_at=datetime(2026, 11, 15, 9, tzinfo=UTC),
        checkpoint_id="checkpoint-1",
        plan=[PlanStep(step_id="check-credit", tool_name="get_settlement_report")],
        events=[
            TaskEvent(kind="read_timeout", message="Settlement report timed out"),
            TaskEvent(kind="retry", message="Retry 1 of 2"),
        ],
        evidence=[
            Evidence(
                evidence_id="evidence-1",
                source="settlement",
                source_reference="settlement-1",
                description="Outstanding credit",
                amount_paise=16680,
            )
        ],
    )
    task.approvals = [
        Approval(
            approval_id="approval-1",
            task_id=task.task_id,
            merchant_id=task.merchant_id,
            action="create_support_ticket",
            approved_inputs={"summary": "Missing credit", "amount_paise": 16680},
            input_hash="inputs-1",
            decision="approved",
            approver=task.merchant_id,
            decided_at=datetime(2026, 11, 14, 9, tzinfo=UTC),
        )
    ]
    task.receipts = [
        Receipt(
            receipt_id="receipt-1",
            task_id=task.task_id,
            external_reference="ticket-1",
            input_hash="inputs-1",
        )
    ]
    task.verifications = [
        Verification(
            verification_id="verification-1",
            receipt_id="receipt-1",
            tool_name="get_ticket_status",
            verified=True,
            evidence_reference="ticket-1",
        )
    ]
    task.executions = [
        ToolExecution(
            execution_id="execution-1",
            task_id=task.task_id,
            tool_name="get_settlement_report",
            input_hash="report-inputs",
            outcome="error",
            error="read timeout",
        )
    ]
    return path, repo.save(task)


def test_full_task_state_survives_repository_reopen(saved_task):
    path, task = saved_task
    restored = SQLiteTaskRepository(path).get_task(task.merchant_id, task.task_id)
    assert restored.model_dump(mode="json") == task.model_dump(mode="json")
    assert restored.revision == 1
    assert restored.status == TaskStatus.WAITING_EXTERNAL
    assert restored.executions[0].error == "read timeout"
    assert restored.checkpoint_id == "checkpoint-1"


@pytest.mark.parametrize("storage", ["memory", "sqlite"])
def test_stale_snapshots_cannot_overwrite_newer_records(tmp_path, storage):
    repo = MemoryTaskRepository() if storage == "memory" else SQLiteTaskRepository(tmp_path / "db")
    original = repo.save(
        Task(
            merchant_id="merchant_demo", goal="goal", original_request="request", next_action="wait"
        )
    )
    first = repo.get_task(original.merchant_id, original.task_id)
    stale = repo.get_task(original.merchant_id, original.task_id)
    first.events.append(TaskEvent(kind="message", message="Preserve this update"))
    updated = repo.save(first)
    stale.goal = "Overwrite latest"
    with pytest.raises(TaskConflictError):
        repo.save(stale)
    assert updated.revision == 2
    assert repo.get_task(original.merchant_id, original.task_id) == updated
    updated.events.clear()
    assert len(repo.get_task(original.merchant_id, original.task_id).events) == 1


def test_concurrent_workers_preserve_one_consistent_snapshot(saved_task):
    path, original = saved_task
    barrier = Barrier(2)

    def update(message):
        repo = SQLiteTaskRepository(path)
        snapshot = repo.get_task(original.merchant_id, original.task_id)
        snapshot.events.append(TaskEvent(kind="worker_update", message=message))
        barrier.wait(timeout=5)
        try:
            return repo.save(snapshot)
        except TaskConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(update, ["worker A", "worker B"]))
    successful = [result for result in results if result is not None]
    assert len(successful) == 1
    restored = SQLiteTaskRepository(path).get_task(original.merchant_id, original.task_id)
    assert restored == successful[0]
    assert restored.revision == 2
    assert len(restored.events) == len(original.events) + 1


def test_serialization_failure_rolls_back_whole_update(saved_task):
    path, original = saved_task
    invalid = original.model_copy(deep=True)
    invalid.plan[0].inputs = {"unserializable": object()}
    invalid.next_action = "Do not persist this partial change"
    repo = SQLiteTaskRepository(path)
    with pytest.raises(PydanticSerializationError):
        repo.save(invalid)
    assert repo.get_task(original.merchant_id, original.task_id) == original
    original.next_action = "A later valid update"
    assert repo.save(original).revision == 2


@pytest.mark.parametrize("storage", ["memory", "sqlite"])
def test_task_order_has_stable_ties_and_is_merchant_scoped(tmp_path, storage):
    repo = MemoryTaskRepository() if storage == "memory" else SQLiteTaskRepository(tmp_path / "db")
    for task_id, merchant_id in [("a", "merchant_demo"), ("b", "merchant_demo"), ("c", "other")]:
        repo.save(
            Task(
                task_id=task_id,
                merchant_id=merchant_id,
                goal="goal",
                original_request="request",
                next_action="wait",
                created_at=datetime(2026, 11, 14, tzinfo=UTC),
            )
        )
    assert [task.task_id for task in repo.list_tasks("merchant_demo")] == ["b", "a"]
    assert repo.get_task("other", "a") is None


@pytest.mark.parametrize("storage", ["memory", "sqlite"])
def test_timeline_orders_mixed_timezones_and_preserves_equal_time_order(tmp_path, storage):
    repo = MemoryTaskRepository() if storage == "memory" else SQLiteTaskRepository(tmp_path / "db")
    task = Task(
        merchant_id="merchant_demo",
        goal="goal",
        original_request="request",
        next_action="wait",
        events=[
            TaskEvent(kind="later", message="later", occurred_at="2026-11-14T10:00:00Z"),
            TaskEvent(kind="first", message="first", occurred_at="2026-11-14T09:00:00"),
            TaskEvent(kind="second", message="second", occurred_at="2026-11-14T14:30:00+05:30"),
        ],
    )
    saved = repo.save(task)
    assert [event.kind for event in saved.events] == ["first", "second", "later"]
    assert repo.get_task(task.merchant_id, task.task_id) == saved


def test_database_path_is_independent_of_startup_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    assert settings.database_file == BACKEND_ROOT / ".data/bizmate.sqlite3"


def test_newer_database_schema_is_rejected(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 2")
    with pytest.raises(RuntimeError, match="newer"):
        SQLiteTaskRepository(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_api_history_survives_separate_processes(tmp_path):
    # Each invocation starts and exits a separate backend process against the same database.
    script = """
import json
import sys
from fastapi.testclient import TestClient
from bizmate.config import Settings
from bizmate.main import create_app

with TestClient(create_app(Settings(_env_file=None, database_path=sys.argv[1]))) as client:
    if sys.argv[2] == "create":
        response = client.post("/api/v1/tasks", json={"message": "Persistent request"})
        assert response.status_code == 201
        task_id = response.json()["task_id"]
        response = client.post(
            f"/api/v1/tasks/{task_id}/messages", json={"message": "Keep my clarification"}
        )
    else:
        response = client.get(f"/api/v1/tasks/{sys.argv[2]}")
    assert response.status_code == 200
    print(json.dumps({"task": response.json(), "tasks": client.get("/api/v1/tasks").json()}))
"""
    path = str(tmp_path / "restart.sqlite3")
    first = subprocess.run(
        [sys.executable, "-c", script, path, "create"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    saved = json.loads(first.stdout)
    second = subprocess.run(
        [sys.executable, "-c", script, path, saved["task"]["task_id"]],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(second.stdout) == saved
    assert saved["task"]["revision"] == 2
    assert saved["task"]["events"][-1]["message"] == "Keep my clarification"
