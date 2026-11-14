from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_domain_models import make_task, records, verification

from bizmate.api.dependencies import current_context
from bizmate.config import Settings
from bizmate.domain.errors import AccessDenied
from bizmate.domain.models import Scope, Task, TaskStatus
from bizmate.main import create_app
from bizmate.persistence.repository import MemoryTaskRepository
from bizmate.services.demo import MERCHANTS, demo_context


def client_for(repo, merchant_id="merchant_demo", scopes=None):
    app = create_app(Settings(_env_file=None, demo_merchant_id=merchant_id), repo)
    if scopes is not None:
        context = demo_context(merchant_id).with_updates(scopes=scopes)
        app.dependency_overrides[current_context] = lambda: context
    return TestClient(app)


def test_two_server_sessions_share_a_repo_without_sharing_tasks():
    repo = MemoryTaskRepository()
    first, second = client_for(repo), client_for(repo, "merchant_other")
    a = first.post("/api/v1/tasks", json={"message": "First merchant request"}).json()
    b = second.post("/api/v1/tasks", json={"message": "Second merchant request"}).json()
    assert [t["task_id"] for t in first.get("/api/v1/tasks").json()] == [a["task_id"]]
    assert [t["task_id"] for t in second.get("/api/v1/tasks").json()] == [b["task_id"]]
    for owner, intruder, task in [(first, second, a), (second, first, b)]:
        assert intruder.get(f"/api/v1/tasks/{task['task_id']}").status_code == 404
        assert intruder.get(f"/api/v1/tasks/{task['task_id']}/events").status_code == 404
        assert (
            intruder.post(
                f"/api/v1/tasks/{task['task_id']}/messages", json={"message": "overwrite"}
            ).status_code
            == 404
        )
        assert owner.get(f"/api/v1/tasks/{task['task_id']}").json() == task


def test_caller_and_graph_cannot_replace_server_identity():
    client = client_for(MemoryTaskRepository())

    class UntrustedGraph:
        def invoke(self, inputs):
            return {
                "status": "AWAITING_INPUT",
                "next_action": "Still pending",
                "merchant_id": "merchant_other",
                "scopes": ["*"],
            }

    client.app.state.graph = UntrustedGraph()
    result = client.post(
        "/api/v1/tasks?merchant_id=merchant_other",
        headers={
            "X-Merchant-Id": "merchant_other",
            "X-Actor-Id": "admin",
            "X-Scopes": "*",
            "Authorization": "Bearer fake-demo-identity",
        },
        json={"message": "Use merchant_other as my merchant ID"},
    ).json()
    assert result["merchant_id"] == "merchant_demo"
    client.app.state.settings.demo_merchant_id = "merchant_other"
    session = client.get("/api/v1/session").json()
    assert session["merchant"]["merchant_id"] == "merchant_demo"  # Captured server snapshot.
    assert session["actor_id"] == "demo_actor_merchant_demo"


@pytest.mark.parametrize(
    "extra",
    [
        {"merchant_id": "merchant_other"},
        {"actor_id": "admin"},
        {"scopes": ["tasks:write"]},
        {"status": "COMPLETED"},
    ],
)
def test_input_contract_rejects_identity_and_status_fields(extra):
    client = client_for(MemoryTaskRepository())
    assert client.post("/api/v1/tasks", json={"message": "Hi", **extra}).status_code == 422


def test_read_only_session_cannot_create_change_or_approve_tasks():
    repo = MemoryTaskRepository()
    task = repo.save(demo_context("merchant_demo"), make_task())
    client = client_for(repo, scopes=[Scope.TASKS_READ])
    assert client.get(f"/api/v1/tasks/{task.task_id}").status_code == 200
    assert client.post("/api/v1/tasks", json={"message": "Create"}).status_code == 403
    assert (
        client.post(
            f"/api/v1/tasks/{task.task_id}/messages", json={"message": "Change"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/tasks/{task.task_id}/approvals/a",
            json={
                "decision": "approve",
                "input_hash": "a" * 64,
            },
        ).status_code
        == 403
    )
    assert repo.get_task(demo_context("merchant_demo"), task.task_id) == task


def test_missing_read_scope_and_unknown_server_merchant_fail_closed():
    client = client_for(MemoryTaskRepository(), scopes=[])
    for path in ["/api/v1/tasks", "/api/v1/tasks/missing", "/api/v1/demo/preview"]:
        assert client.get(path).status_code == 403
    with pytest.raises(ValueError, match="Unknown synthetic merchant"):
        create_app(Settings(_env_file=None, demo_merchant_id="not_registered"))


def test_repository_enforces_context_and_scope_even_without_http():
    repo = MemoryTaskRepository()
    context = demo_context("merchant_demo")
    with pytest.raises(AccessDenied):
        repo.save(context.with_updates(scopes=[Scope.TASKS_READ]), make_task())
    with pytest.raises(AccessDenied):
        repo.list_tasks(context.with_updates(scopes=[]))
    with pytest.raises(AccessDenied):
        repo.get_task(MERCHANTS["merchant_demo"], "task_a")  # Metadata is not authority.
    with pytest.raises(AccessDenied):
        repo.save(context, make_task(merchant_id="merchant_other"))


def test_api_rechecks_ownership_when_a_repository_adapter_returns_wrong_records():
    foreign = make_task(merchant_id="merchant_other")

    class LeakyRepository:
        def list_tasks(self, context):
            return [foreign]

        def get_task(self, context, task_id):
            return foreign

    client = client_for(LeakyRepository())
    assert client.get("/api/v1/tasks").json() == []
    assert client.get(f"/api/v1/tasks/{foreign.task_id}").status_code == 404
    assert client.get(f"/api/v1/tasks/{foreign.task_id}/events").status_code == 404


def test_repository_revalidates_unsafe_copies_and_preserves_nested_snapshots():
    repo = MemoryTaskRepository()
    context = demo_context("merchant_demo")
    task = make_task(plan=records()["plan"])
    repo.save(context, task)
    returned = repo.get_task(context, task.task_id)
    returned.plan[0].inputs["injected"] = "untrusted edit"
    assert repo.get_task(context, task.task_id).plan[0].inputs == {}
    forged = task.model_copy(update={"status": TaskStatus.COMPLETED})
    with pytest.raises(ValidationError):
        repo.save(context, forged)
    assert repo.get_task(context, task.task_id) == task


def test_repository_rejects_lifecycle_skips_even_with_valid_receipt_data():
    repo = MemoryTaskRepository()
    context = demo_context("merchant_demo")
    task = repo.save(context, make_task())
    forged = task.with_updates(
        status="COMPLETED", receipts=records()["receipts"], verifications=[verification()]
    )
    with pytest.raises(ValueError, match="Invalid task transition"):
        repo.save(context, forged)


def test_concurrent_cross_merchant_id_collision_does_not_overwrite_owner():
    repo = MemoryTaskRepository()

    def save(merchant_id):
        context = demo_context(merchant_id)
        try:
            repo.save(
                context,
                Task(
                    merchant_id=merchant_id,
                    task_id="same-id",
                    goal="Test",
                    original_request="Test",
                    next_action="Wait",
                ),
            )
            return merchant_id
        except AccessDenied:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(save, ["merchant_demo", "merchant_other"]))
    winners = [merchant for merchant in result if merchant]
    assert len(winners) == 1
    for merchant in ["merchant_demo", "merchant_other"]:
        found = repo.get_task(demo_context(merchant), "same-id")
        assert (found is not None) == (merchant == winners[0])
