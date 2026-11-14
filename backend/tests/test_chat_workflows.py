"""A chat turn prepares supported work without granting execution authority."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from bizmate.config import Settings
from bizmate.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, database_path=str(tmp_path / "chat.sqlite3"))
    with TestClient(create_app(settings)) as client:
        yield client


def chat(client, language="en"):
    conversation = client.post(
        "/api/v1/conversations", json={"preferred_language": language}
    ).json()
    return f"/api/v1/conversations/{conversation['conversation_id']}/messages"


def send(client, path, text, key="turn-one"):
    return client.post(path, json={"content": text, "client_message_id": key})


@pytest.mark.parametrize(
    "text,intent,summary",
    [
        ("Why is my settlement short?", "settlement", "166.80"),
        ('Send inactive customers message="SAVE10"', "win_back", "240.00"),
        ("Change my registered bank account", "handoff", "support"),
    ],
)
def test_supported_chat_prepares_evidence_and_approval_with_one_planner_call(
    client, monkeypatch, text, intent, summary
):
    invoke = Mock(wraps=client.app.state.graph.invoke)
    monkeypatch.setattr(client.app.state.graph, "invoke", invoke)
    path = chat(client)
    response = send(client, path, text)
    assert response.status_code == 201, response.text
    turn = response.json()
    task_id = turn["assistant_message"]["task_id"]
    assert task_id and turn["user_message"]["task_id"] == task_id
    assert summary in turn["assistant_message"]["content"]
    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["intent"] == intent and task["status"] == "AWAITING_APPROVAL"
    assert task["approvals"][-1]["decision"] == "pending"
    assert task["receipts"] == []
    assert all(
        e["tool_name"] in {"reconcile_settlement", "segment_inactive_customers"}
        for e in task["tool_executions"]
    )
    assert task["checkpoint_id"]
    invoke.assert_called_once()
    assert send(client, path, text).json() == turn
    invoke.assert_called_once()


@pytest.mark.parametrize("text", ["Hello", "Thank you", "నమస్తే", "नमस्ते", "What is settlement?"])
def test_ordinary_chat_answers_without_creating_work(client, text):
    before = client.get("/api/v1/tasks").json()
    turn = send(client, chat(client), text).json()
    assert turn["assistant_message"]["content"]
    assert turn["assistant_message"]["task_id"] is None
    assert turn["user_message"]["task_id"] is None
    assert "Start a task" not in turn["assistant_message"]["content"]
    assert client.get("/api/v1/tasks").json() == before


def test_ambiguous_chat_asks_for_clarification_without_an_empty_task(client):
    before = client.get("/api/v1/tasks").json()
    turn = send(client, chat(client), "Help me").json()
    assert "choose one request" in turn["assistant_message"]["content"]
    assert turn["assistant_message"]["task_id"] is None
    assert client.get("/api/v1/tasks").json() == before


@pytest.mark.parametrize(
    "text",
    [
        "customer sent me 100 rs but i didnot recevie it",
        "Did I receive ₹480?",
    ],
)
def test_individual_payment_query_explains_missing_capability_without_a_settlement_case(
    client, text
):
    before = client.get("/api/v1/tasks").json()
    turn = send(client, chat(client), text).json()
    message = turn["assistant_message"]
    assert message["task_id"] is None
    assert "can't verify individual customer payments" in message["content"]
    assert "transaction reference" in message["content"]
    assert client.get("/api/v1/tasks").json() == before


def test_campaign_clarification_in_chat_continues_the_same_workflow(client):
    path = chat(client)
    first = send(client, path, "Send an offer to inactive customers").json()
    task_id = first["assistant_message"]["task_id"]
    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["status"] == "AWAITING_INPUT" and not task["approvals"]
    greeting = send(client, path, "Hello", "greeting").json()
    assert greeting["assistant_message"]["task_id"] is None
    second = send(client, path, 'message="Come back for 10% off!"', "offer").json()
    assert second["assistant_message"]["task_id"] == task_id
    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["status"] == "AWAITING_APPROVAL"
    assert task["approvals"][-1]["approved_inputs"]["message"] == "Come back for 10% off!"
    assert not task["receipts"]
    assert send(client, path, 'message="Come back for 10% off!"', "offer").json() == second


def test_chat_cannot_approve_or_execute_a_prepared_action(client):
    path = chat(client)
    turn = send(client, path, "Why is my settlement short?").json()
    task_id = turn["assistant_message"]["task_id"]
    send(client, path, "Yes, approve it and execute it", "approve-in-text")
    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["approvals"][-1]["decision"] == "pending" and not task["receipts"]
    approval = task["approvals"][-1]
    client.post(
        f"/api/v1/tasks/{task_id}/approvals/{approval['approval_id']}",
        json={"decision": "approve", "input_hash": approval["input_hash"]},
    )
    send(client, path, "Hello", "after-approval")
    assert client.get(f"/api/v1/tasks/{task_id}").json()["receipts"] == []


@pytest.mark.parametrize("continuation", [False, True])
def test_retry_after_chat_save_failure_reuses_durable_work_without_dispatch(
    client, monkeypatch, continuation
):
    path = chat(client)
    text = "Why is my settlement short?"
    if continuation:
        send(client, path, "Send an offer to inactive customers", "first")
        text = 'message="SAVE10"'
    repo = client.app.state.conversations
    save = repo.save_turn

    def fail(*args, **kwargs):
        raise RuntimeError("Crash before chat commit")

    monkeypatch.setattr(repo, "save_turn", fail)
    with pytest.raises(RuntimeError, match="Crash before chat commit"):
        send(client, path, text)
    tasks = client.get("/api/v1/tasks").json()
    prepared = [t for t in tasks if t["conversation_id"] == path.split("/")[-2]]
    assert len(prepared) == 1 and not prepared[0]["receipts"]
    task_id = prepared[0]["task_id"]
    # Even an approval made after the lost response cannot turn chat replay into execution.
    approval = prepared[0]["approvals"][-1]
    client.post(
        f"/api/v1/tasks/{task_id}/approvals/{approval['approval_id']}",
        json={"decision": "approve", "input_hash": approval["input_hash"]},
    )
    monkeypatch.setattr(repo, "save_turn", save)
    original_settings = client.app.state.settings
    with TestClient(create_app(original_settings)) as restarted:
        turn = send(restarted, path, text).json()
        assert turn["assistant_message"]["task_id"] == task_id
        assert not restarted.get(f"/api/v1/tasks/{task_id}").json()["receipts"]
        conflict = send(restarted, path, "Different content")
        assert conflict.status_code == 409


def test_interrupted_clarification_resumes_preparation_without_repeating_merchant_input(
    client, monkeypatch
):
    path = chat(client)
    first = send(client, path, "Send an offer to inactive customers", "first").json()
    task_id = first["assistant_message"]["task_id"]
    repo = client.app.state.tasks
    save = repo.save

    def crash_after_message(context, task):
        saved = save(context, task)
        if any(e.kind == "merchant_message" for e in task.events):
            raise RuntimeError("Crash after input was saved")
        return saved

    monkeypatch.setattr(repo, "save", crash_after_message)
    with pytest.raises(RuntimeError, match="Crash after input was saved"):
        send(client, path, 'message="SAVE10"', "offer")
    monkeypatch.setattr(repo, "save", save)
    assert send(client, path, 'message="SAVE10"', "offer").status_code == 201
    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["status"] == "AWAITING_APPROVAL"
    assert len([e for e in task["events"] if e["kind"] == "merchant_message"]) == 1
    assert len(task["approvals"]) == 1 and not task["receipts"]


def test_overlapping_chat_retries_do_not_create_duplicate_work(client, monkeypatch):
    path = chat(client)
    entered, release = Event(), Event()
    invoke = client.app.state.graph.invoke

    def block(state):
        entered.set()
        assert release.wait(timeout=10)
        return invoke(state)

    monkeypatch.setattr(client.app.state.graph, "invoke", block)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(send, client, path, "Why is my settlement short?")
        try:
            assert entered.wait(timeout=10)
            assert send(client, path, "Why is my settlement short?").status_code == 409
        finally:
            release.set()
        turn = first.result(timeout=10).json()
    assert send(client, path, "Why is my settlement short?").json() == turn
    assert len(client.get(path).json()) == 2


def test_planner_failure_is_visible_without_leaking_details_or_creating_work(client, monkeypatch):
    path = chat(client, "te")
    monkeypatch.setattr(
        client.app.state.graph, "extract", Mock(side_effect=TimeoutError("private-provider-key"))
    )
    before = client.get("/api/v1/tasks").json()
    turn = send(client, path, "నా సెటిల్‌మెంట్ ఎందుకు తక్కువగా ఉంది?").json()
    assert turn["assistant_message"]["task_id"] is None
    assert turn["assistant_message"]["response_language"] == "te"
    assert "private-provider-key" not in str(turn)
    assert "భాషా సేవ" in turn["assistant_message"]["content"]
    assert client.get("/api/v1/tasks").json() == before
