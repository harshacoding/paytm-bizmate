import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import pytest
from pydantic import ValidationError
from test_domain_models import STAMP, make_task, records, verification

from bizmate.config import BACKEND_ROOT, Settings
from bizmate.domain.models import (
    Task,
    TaskEvent,
    TaskStatus,
)
from bizmate.persistence.repository import MemoryTaskRepository, TaskConflictError
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import demo_context


@pytest.fixture
def saved_task(tmp_path):
    path = tmp_path / "nested" / "tasks.sqlite3"
    repo = SQLiteTaskRepository(path)
    attached = records()
    attached["approvals"] = tuple(
        item.with_updates(decision="approved", approver="merchant_demo", decided_at=STAMP)
        for item in attached["approvals"]
    )
    attached["tool_executions"] = tuple(
        item.with_updates(outcome="failed", error="read timeout")
        for item in attached["tool_executions"]
    )
    task = make_task(
        **attached,
        status=TaskStatus.WAITING_EXTERNAL,
        next_action="Read fresh settlement evidence",
        next_run_at=datetime(2026, 11, 15, 9, tzinfo=UTC),
        checkpoint_id="checkpoint-1",
        verifications=(verification(),),
        events=(
            TaskEvent(kind="read_timeout", message="Settlement report timed out"),
            TaskEvent(kind="retry", message="Retry 1 of 2"),
        ),
    )
    return path, repo.save(demo_context("merchant_demo"), task)


def test_full_task_state_survives_repository_reopen(saved_task):
    path, task = saved_task
    restored = SQLiteTaskRepository(path).get_task(demo_context(task.merchant_id), task.task_id)
    assert restored.model_dump(mode="json") == task.model_dump(mode="json")
    assert restored.revision == 1
    assert restored.status == TaskStatus.WAITING_EXTERNAL
    assert restored.tool_executions[0].error == "read timeout"
    assert restored.checkpoint_id == "checkpoint-1"


def test_pre_contract_task_records_remain_readable_and_auditable(saved_task):
    path, original = saved_task
    legacy = json.loads(original.model_dump_json())
    legacy["executions"] = legacy.pop("tool_executions")
    for field in ["plan", "evidence", "receipts", "verifications", "executions"]:
        for item in legacy[field]:
            item.pop("merchant_id", None)
            item.pop("task_id", None)
    for item in legacy["executions"]:
        item["outcome"] = "error"
        item["input_hash"] = "legacy-report-inputs"
    for item in legacy["receipts"]:
        item.pop("action")
        item.pop("idempotency_key")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE tasks SET payload = ? WHERE task_id = ?", (json.dumps(legacy), original.task_id)
        )
    restored = SQLiteTaskRepository(path).get_task(
        demo_context(original.merchant_id), original.task_id
    )
    assert restored.tool_executions[0].outcome == "failed"
    assert restored.receipts[0].action == restored.approvals[0].action
    assert restored.workflow_data["legacy_input_hashes"]["legacy-report-inputs"]
    assert restored.checkpoint_id == original.checkpoint_id


@pytest.mark.parametrize("storage", ["memory", "sqlite"])
def test_stale_snapshots_cannot_overwrite_newer_records(tmp_path, storage):
    repo = MemoryTaskRepository() if storage == "memory" else SQLiteTaskRepository(tmp_path / "db")
    original = repo.save(
        demo_context("merchant_demo"),
        Task(
            merchant_id="merchant_demo", goal="goal", original_request="request", next_action="wait"
        ),
    )
    first = repo.get_task(demo_context(original.merchant_id), original.task_id)
    stale = repo.get_task(demo_context(original.merchant_id), original.task_id)
    first = first.with_updates(
        events=(*first.events, TaskEvent(kind="message", message="Preserve this update"))
    )
    updated = repo.save(demo_context("merchant_demo"), first)
    stale = stale.with_updates(goal="Overwrite latest")
    with pytest.raises(TaskConflictError):
        repo.save(demo_context("merchant_demo"), stale)
    assert updated.revision == 2
    assert repo.get_task(demo_context(original.merchant_id), original.task_id) == updated
    updated.workflow_data["detached_edit"] = True
    assert len(repo.get_task(demo_context(original.merchant_id), original.task_id).events) == 1


def test_concurrent_workers_preserve_one_consistent_snapshot(saved_task):
    path, original = saved_task
    barrier = Barrier(2)

    def update(message):
        repo = SQLiteTaskRepository(path)
        snapshot = repo.get_task(demo_context(original.merchant_id), original.task_id)
        snapshot = snapshot.with_updates(
            events=(*snapshot.events, TaskEvent(kind="worker_update", message=message))
        )
        barrier.wait(timeout=5)
        try:
            return repo.save(demo_context("merchant_demo"), snapshot)
        except TaskConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(update, ["worker A", "worker B"]))
    successful = [result for result in results if result is not None]
    assert len(successful) == 1
    restored = SQLiteTaskRepository(path).get_task(
        demo_context(original.merchant_id), original.task_id
    )
    assert restored == successful[0]
    assert restored.revision == 2
    assert len(restored.events) == len(original.events) + 1


def test_serialization_failure_rolls_back_whole_update(saved_task):
    path, original = saved_task
    invalid = original.model_copy(deep=True)
    invalid.plan[0].inputs["unserializable"] = object()
    invalid = invalid.model_copy(update={"next_action": "Do not persist this partial change"})
    repo = SQLiteTaskRepository(path)
    with pytest.raises(ValidationError):
        repo.save(demo_context("merchant_demo"), invalid)
    assert repo.get_task(demo_context(original.merchant_id), original.task_id) == original
    original = original.with_updates(next_action="A later valid update")
    assert repo.save(demo_context("merchant_demo"), original).revision == 2


@pytest.mark.parametrize("storage", ["memory", "sqlite"])
def test_task_order_has_stable_ties_and_is_merchant_scoped(tmp_path, storage):
    repo = MemoryTaskRepository() if storage == "memory" else SQLiteTaskRepository(tmp_path / "db")
    for task_id, merchant_id in [
        ("a", "merchant_demo"),
        ("b", "merchant_demo"),
        ("c", "merchant_other"),
    ]:
        repo.save(
            demo_context(merchant_id),
            Task(
                task_id=task_id,
                merchant_id=merchant_id,
                goal="goal",
                original_request="request",
                next_action="wait",
                created_at=datetime(2026, 11, 14, tzinfo=UTC),
            ),
        )
    assert [task.task_id for task in repo.list_tasks(demo_context("merchant_demo"))] == ["b", "a"]
    assert repo.get_task(demo_context("merchant_other"), "a") is None


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
            TaskEvent(kind="first", message="first", occurred_at="2026-11-14T09:00:00Z"),
            TaskEvent(kind="second", message="second", occurred_at="2026-11-14T14:30:00+05:30"),
        ],
    )
    saved = repo.save(demo_context("merchant_demo"), task)
    assert [event.kind for event in saved.events] == ["first", "second", "later"]
    assert repo.get_task(demo_context(task.merchant_id), task.task_id) == saved


def test_database_path_is_independent_of_startup_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    assert settings.database_file == BACKEND_ROOT / ".data/bizmate.sqlite3"


def test_newer_database_schema_is_rejected(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 3")
    with pytest.raises(RuntimeError, match="newer"):
        SQLiteTaskRepository(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3


def test_api_history_survives_separate_processes(tmp_path):
    # Each invocation starts and exits a separate backend process against the same database.
    script = """
import json
import sys
from fastapi.testclient import TestClient
from bizmate.config import Settings
from bizmate.main import create_app
from bizmate.services.demo import demo_context

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
