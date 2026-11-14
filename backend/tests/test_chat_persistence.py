import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from bizmate.api.dependencies import current_context
from bizmate.config import Settings
from bizmate.domain.models import Scope, Task, TaskStatus
from bizmate.main import create_app
from bizmate.persistence.conversations import (
    ConversationConflictError,
    SQLiteConversationRepository,
)
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import demo_context


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, database_path=str(tmp_path / "bizmate.sqlite3"))


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def test_create_list_detail_and_both_message_roles(client):
    before = client.get("/api/v1/tasks").json()
    response = client.post("/api/v1/conversations", json={"title": "  Settlement questions  "})
    assert response.status_code == 201
    conversation = response.json()
    conversation_id = conversation["conversation_id"]
    assert conversation["title"] == "Settlement questions"
    assert conversation["merchant_id"] == "merchant_demo"
    assert client.get("/api/v1/conversations").json() == [conversation]
    assert client.get(f"/api/v1/conversations/{conversation_id}").json() == conversation
    assert client.get(f"/api/v1/conversations/{conversation_id}/messages").json() == []

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "  Why is my settlement short?  ", "client_message_id": "first-turn"},
    )
    assert response.status_code == 201
    turn = response.json()
    assert turn["client_message_id"] == "first-turn"
    assert turn["user_message"]["role"] == "user"
    assert turn["user_message"]["content"] == "  Why is my settlement short?  "
    assert turn["assistant_message"]["role"] == "assistant"
    assert "Request understood" in turn["assistant_message"]["content"]
    assert turn["user_message"]["sequence"] == 1
    assert turn["assistant_message"]["sequence"] == 2
    history = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()
    assert history == [turn["user_message"], turn["assistant_message"]]
    assert client.get("/api/v1/tasks").json() == before


def test_retry_returns_existing_turn_without_reinvoking_graph(client, monkeypatch):
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation_id"]
    path = f"/api/v1/conversations/{conversation_id}/messages"
    body = {"content": "Save my question", "client_message_id": "retry-key"}
    original = client.post(path, json=body).json()

    def unexpected_call(*args, **kwargs):
        raise AssertionError("A replay must retrieve the persisted assistant response")

    monkeypatch.setattr(client.app.state.graph, "invoke", unexpected_call)
    assert client.post(path, json=body).json() == original
    conflict = client.post(path, json={**body, "content": "A different question"})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "MESSAGE_CONFLICT"
    assert len(client.get(path).json()) == 2


def test_cross_merchant_reads_and_writes_are_blocked(settings, client):
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation_id"]
    path = f"/api/v1/conversations/{conversation_id}"
    client.post(path + "/messages", json={"content": "Private question"})
    other_settings = Settings(
        _env_file=None, database_path=settings.database_path, demo_merchant_id="merchant_other"
    )
    with TestClient(create_app(other_settings)) as other:
        assert other.get("/api/v1/conversations").json() == []
        assert other.get(path).status_code == 404
        assert other.get(path + "/messages").status_code == 404
        assert (
            other.post(path + "/messages", json={"content": "Attempt mutation"}).status_code == 404
        )
        own = other.post("/api/v1/conversations", json={}).json()
        assert own["merchant_id"] == "merchant_other"
        assert client.get(f"/api/v1/conversations/{own['conversation_id']}").status_code == 404
    assert len(client.get(path + "/messages").json()) == 2


@pytest.mark.parametrize("override", ["merchant_id", "conversation_id", "role", "task_id"])
def test_message_body_cannot_override_server_fields(client, override):
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation_id"]
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Hello", override: "forged"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_header_query_and_message_text_do_not_override_identity(client):
    response = client.post(
        "/api/v1/conversations?merchant_id=merchant_other",
        headers={"X-Merchant-Id": "merchant_other"},
        json={"title": "merchant_id=merchant_other"},
    )
    assert response.json()["merchant_id"] == "merchant_demo"
    invalid = client.post("/api/v1/conversations", json={"merchant_id": "merchant_other"})
    assert invalid.status_code == 422


@pytest.mark.parametrize("content", ["", "  ", "x" * 4001])
def test_invalid_messages_are_rejected_without_history_changes(client, content):
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation_id"]
    path = f"/api/v1/conversations/{conversation_id}/messages"
    assert client.post(path, json={"content": content}).status_code == 422
    assert client.get(path).json() == []


def test_missing_conversations_return_same_not_found_contract(client):
    for response in [
        client.get("/api/v1/conversations/missing"),
        client.get("/api/v1/conversations/missing/messages"),
        client.post("/api/v1/conversations/missing/messages", json={"content": "Hello"}),
    ]:
        assert response.status_code == 404
        assert response.json() == {
            "code": "NOT_FOUND",
            "message": "Conversation not found",
            "task_reference": None,
        }


def test_history_and_stable_ids_survive_app_restart(settings, client):
    conversation = client.post("/api/v1/conversations", json={"title": "Persistent chat"}).json()
    path = f"/api/v1/conversations/{conversation['conversation_id']}"
    turn = client.post(path + "/messages", json={"content": "Remember this question"}).json()
    with TestClient(create_app(settings)) as restarted:
        assert (
            restarted.get("/api/v1/conversations").json()[0]["conversation_id"]
            == conversation["conversation_id"]
        )
        assert restarted.get(path).json()["title"] == "Persistent chat"
        assert restarted.get(path + "/messages").json() == [
            turn["user_message"],
            turn["assistant_message"],
        ]


def test_concurrent_turns_have_contiguous_sequences_and_retries_are_atomic(tmp_path):
    path = tmp_path / "concurrency.sqlite3"
    repo = SQLiteConversationRepository(path)
    conversation = repo.create(demo_context("merchant_demo"), "Concurrent chat")
    barrier = Barrier(4)

    def write(index):
        worker = SQLiteConversationRepository(path)
        barrier.wait(timeout=5)
        return worker.save_turn(
            demo_context("merchant_demo"),
            conversation.conversation_id,
            f"Question {index}",
            f"Answer {index}",
            f"turn-{index}",
        )

    with ThreadPoolExecutor(max_workers=4) as workers:
        turns = list(workers.map(write, range(4)))
    history = repo.messages(demo_context("merchant_demo"), conversation.conversation_id)
    assert [message.sequence for message in history] == list(range(1, 9))
    assert [message.role for message in history] == ["user", "assistant"] * 4
    for turn in turns:
        assert turn.assistant_message.sequence == turn.user_message.sequence + 1
        assert (
            repo.save_turn(
                demo_context("merchant_demo"),
                conversation.conversation_id,
                turn.user_message.content,
                "A regenerated answer",
                turn.client_message_id,
            )
            == turn
        )
    assert len(repo.messages(demo_context("merchant_demo"), conversation.conversation_id)) == 8


def test_parallel_retries_with_same_client_id_store_one_turn(tmp_path):
    path = tmp_path / "retry.sqlite3"
    repo = SQLiteConversationRepository(path)
    conversation = repo.create(demo_context("merchant_demo"), "Retry test")
    barrier = Barrier(2)

    def write(index):
        worker = SQLiteConversationRepository(path)
        barrier.wait(timeout=5)
        return worker.save_turn(
            demo_context("merchant_demo"),
            conversation.conversation_id,
            "Same question",
            f"Answer {index}",
            "same-id",
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        turns = list(workers.map(write, range(2)))
    assert turns[0] == turns[1]
    assert len(repo.messages(demo_context("merchant_demo"), conversation.conversation_id)) == 2
    with pytest.raises(ConversationConflictError):
        repo.save_turn(
            demo_context("merchant_demo"),
            conversation.conversation_id,
            "Changed question",
            "Answer",
            "same-id",
        )


def test_failed_assistant_insert_rolls_back_user_message_and_conversation_update(tmp_path):
    repo = SQLiteConversationRepository(tmp_path / "rollback.sqlite3")
    conversation = repo.create(demo_context("merchant_demo"), "Atomic turns")
    with pytest.raises(ValidationError):
        repo.save_turn(
            demo_context("merchant_demo"),
            conversation.conversation_id,
            "A valid question",
            "",
            "turn",
        )
    assert repo.messages(demo_context("merchant_demo"), conversation.conversation_id) == []
    assert repo.get(demo_context("merchant_demo"), conversation.conversation_id) == conversation


def test_repository_blocks_cross_merchant_mutations_and_foreign_keys(tmp_path):
    repo = SQLiteConversationRepository(tmp_path / "ownership.sqlite3")
    conversation = repo.create(demo_context("merchant_demo"), "Private")
    assert repo.get(demo_context("merchant_other"), conversation.conversation_id) is None
    assert repo.messages(demo_context("merchant_other"), conversation.conversation_id) is None
    assert (
        repo.get_turn(demo_context("merchant_other"), conversation.conversation_id, "turn") is None
    )
    with pytest.raises(KeyError):
        repo.save_turn(
            demo_context("merchant_other"),
            conversation.conversation_id,
            "Question",
            "Answer",
            "turn",
        )
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO messages (message_id, conversation_id, merchant_id,
                   client_message_id, role, content, sequence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "message",
                    conversation.conversation_id,
                    "merchant_other",
                    "turn",
                    "user",
                    "Attempted forgery",
                    1,
                    "2026-11-14T09:00:00+00:00",
                ),
            )


def test_chat_lifetime_does_not_change_task_status_due_time_or_checkpoint(settings, client):
    repo = SQLiteTaskRepository(settings.database_file)
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation_id"]
    task = repo.save(
        demo_context("merchant_demo"),
        Task(
            merchant_id="merchant_demo",
            goal="Continue independently",
            original_request="Investigate settlement",
            next_action="Check fresh credit",
            status=TaskStatus.WAITING_EXTERNAL,
            checkpoint_id="durable-task-checkpoint",
            conversation_id=conversation_id,
            next_run_at="2026-11-15T09:00:00Z",
        ),
    )
    client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"content": "Hello"})
    with sqlite3.connect(settings.database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,)
        )
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
        assert restarted.get(f"/api/v1/tasks/{task.task_id}").json() == task.model_dump(mode="json")
    with sqlite3.connect(settings.database_file) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (conversation_id,)
            ).fetchone()[0]
            == 0
        )


def test_conversation_history_survives_separate_backend_processes(tmp_path):
    script = """
import json
import sys
from fastapi.testclient import TestClient
from bizmate.config import Settings
from bizmate.main import create_app
from bizmate.services.demo import demo_context
with TestClient(create_app(Settings(_env_file=None, database_path=sys.argv[1]))) as client:
    if sys.argv[2] == "create":
        response = client.post("/api/v1/conversations", json={"title": "Restart test"})
        assert response.status_code == 201
        conversation_id = response.json()["conversation_id"]
        response = client.post(f"/api/v1/conversations/{conversation_id}/messages",
                               json={"content": "Preserve user and assistant history"})
        assert response.status_code == 201
    else:
        conversation_id = sys.argv[2]
    conversation_path = f"/api/v1/conversations/{conversation_id}"
    print(json.dumps({"conversation": client.get(conversation_path).json(),
                      "messages": client.get(conversation_path + "/messages").json()}))
"""
    path = str(tmp_path / "process-restart.sqlite3")
    first = subprocess.run(
        [sys.executable, "-c", script, path, "create"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    saved = json.loads(first.stdout)
    second = subprocess.run(
        [sys.executable, "-c", script, path, saved["conversation"]["conversation_id"]],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(second.stdout) == saved
    assert [message["role"] for message in saved["messages"]] == ["user", "assistant"]


def test_language_preferences_and_original_content_survive_restart(settings, client):
    conversation = client.post(
        "/api/v1/conversations", json={"title": "తెలుగు ప్రశ్నలు", "preferred_language": "te"}
    ).json()
    path = f"/api/v1/conversations/{conversation['conversation_id']}"
    original = "  నా సెటిల్మెంట్ ఎందుకు తక్కువగా వచ్చింది?\nదయచేసి వివరించండి.  "
    turn = client.post(
        path + "/messages", json={"content": original, "client_message_id": "telugu"}
    ).json()
    assert turn["user_message"]["content"] == original
    assert turn["user_message"]["language"] == "te"
    assert turn["assistant_message"]["language"] == "te"
    assert turn["user_message"]["created_at"]
    assert turn["assistant_message"]["created_at"]
    changed = client.patch(path, json={"preferred_language": "hi"})
    assert changed.status_code == 200
    assert changed.json()["preferred_language"] == "hi"
    # Updating a preference leaves the original stored message and retry response intact.
    assert (
        client.post(
            path + "/messages", json={"content": original, "client_message_id": "telugu"}
        ).json()
        == turn
    )
    conflict = client.post(
        path + "/messages",
        json={"content": original, "client_message_id": "telugu", "language": "hi"},
    )
    assert conflict.status_code == 409
    override = client.post(
        path + "/messages", json={"content": "English question", "language": "en"}
    ).json()
    assert override["user_message"]["language"] == "en"
    inherited = client.post(path + "/messages", json={"content": "मेरे प्रश्न का जवाब दें"}).json()
    assert inherited["user_message"]["language"] == "hi"
    history = client.get(path + "/messages").json()
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(path).json()["preferred_language"] == "hi"
        assert restarted.get(path + "/messages").json() == history


@pytest.mark.parametrize("language", ["", "not a language", "1", "en_India"])
def test_invalid_language_metadata_is_rejected(client, language):
    assert (
        client.post("/api/v1/conversations", json={"preferred_language": language}).status_code
        == 422
    )
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation_id"]
    path = f"/api/v1/conversations/{conversation_id}"
    assert client.patch(path, json={"preferred_language": language}).status_code == 422
    assert (
        client.post(path + "/messages", json={"content": "Hello", "language": language}).status_code
        == 422
    )
    assert client.get(path + "/messages").json() == []


def test_conversations_load_oldest_first_even_after_new_messages(client):
    conversations = [
        client.post("/api/v1/conversations", json={"title": title}).json()
        for title in ["First", "Second", "Third"]
    ]
    first_id = conversations[0]["conversation_id"]
    client.post(f"/api/v1/conversations/{first_id}/messages", json={"content": "Recent activity"})
    assert [item["conversation_id"] for item in client.get("/api/v1/conversations").json()] == [
        item["conversation_id"] for item in conversations
    ]


def test_task_association_is_optional_scoped_and_durable(settings, client):
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation_id"]
    linked = client.post(
        "/api/v1/tasks",
        json={"message": "Investigate settlement", "conversation_id": conversation_id},
    )
    assert linked.status_code == 201
    linked = linked.json()
    assert linked["conversation_id"] == conversation_id
    standalone = client.post("/api/v1/tasks", json={"message": "An independent task"}).json()
    assert standalone["conversation_id"] is None
    assert client.get("/api/v1/tasks", params={"conversation_id": conversation_id}).json() == [
        linked
    ]
    other_settings = Settings(
        _env_file=None, database_path=settings.database_path, demo_merchant_id="merchant_other"
    )
    with TestClient(create_app(other_settings)) as other:
        assert (
            other.post(
                "/api/v1/tasks",
                json={"message": "Cross-merchant association", "conversation_id": conversation_id},
            ).status_code
            == 404
        )
        assert (
            other.patch(
                f"/api/v1/conversations/{conversation_id}", json={"preferred_language": "hi"}
            ).status_code
            == 404
        )
        assert other.get("/api/v1/tasks", params={"conversation_id": conversation_id}).json() == []
    assert (
        client.post(
            "/api/v1/tasks", json={"message": "Missing association", "conversation_id": "missing"}
        ).status_code
        == 404
    )
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/v1/tasks/{linked['task_id']}").json() == linked
    with sqlite3.connect(settings.database_file) as connection:
        assert (
            connection.execute(
                "SELECT conversation_id FROM tasks WHERE task_id = ?", (linked["task_id"],)
            ).fetchone()[0]
            == conversation_id
        )


def test_existing_chat_tables_gain_language_fields_without_losing_messages(tmp_path):
    path = tmp_path / "old-chat.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE conversations (
            conversation_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, title TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE (conversation_id, merchant_id))""")
        connection.execute("""CREATE TABLE messages (
            message_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, merchant_id TEXT NOT NULL,
            client_message_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
            sequence INTEGER NOT NULL, created_at TEXT NOT NULL)""")
        connection.execute(
            "INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
            (
                "legacy-chat",
                "merchant_demo",
                "Original",
                "2026-11-14T09:00:00Z",
                "2026-11-14T09:00:00Z",
            ),
        )
        for sequence, role in [(1, "user"), (2, "assistant")]:
            connection.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"legacy-{sequence}",
                    "legacy-chat",
                    "merchant_demo",
                    "legacy-turn",
                    role,
                    f"Original {role} message",
                    sequence,
                    "2026-11-14T09:00:00Z",
                ),
            )
    repo = SQLiteConversationRepository(path)
    assert repo.get(demo_context("merchant_demo"), "legacy-chat").preferred_language == "en"
    history = repo.messages(demo_context("merchant_demo"), "legacy-chat")
    assert [message.content for message in history] == [
        "Original user message",
        "Original assistant message",
    ]
    assert [message.language for message in history] == ["und", "und"]
    assert (
        repo.save_turn(
            demo_context("merchant_demo"), "legacy-chat", "Next question", "Next answer", "next"
        ).user_message.sequence
        == 3
    )


def test_task_schema_migration_preserves_old_task_payloads(tmp_path):
    path = tmp_path / "old-tasks.sqlite3"
    task = Task(
        merchant_id="merchant_demo",
        goal="Existing task",
        original_request="Original request",
        next_action="Continue",
        checkpoint_id="existing-checkpoint",
        revision=1,
    )
    payload = task.model_dump(mode="json")
    payload.pop("conversation_id")
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, created_at TEXT NOT NULL,
            revision INTEGER NOT NULL, payload TEXT NOT NULL)""")
        connection.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
            (task.task_id, task.merchant_id, task.created_at.isoformat(), 1, json.dumps(payload)),
        )
        connection.execute("PRAGMA user_version = 1")
    repo = SQLiteTaskRepository(path)
    restored = repo.get_task(demo_context(task.merchant_id), task.task_id)
    assert restored == task
    assert restored.conversation_id is None
    restored = restored.with_updates(next_action="Updated after migration")
    assert repo.save(demo_context("merchant_demo"), restored).revision == 2


def test_backend_language_metadata_is_distinct_from_declared_preference(
    settings, client, monkeypatch
):
    conversation_id = client.post(
        "/api/v1/conversations", json={"preferred_language": "en"}
    ).json()["conversation_id"]
    path = f"/api/v1/conversations/{conversation_id}"
    monkeypatch.setattr(
        client.app.state.graph,
        "invoke",
        lambda inputs: {
            "next_action": "మీ అభ్యర్థన భద్రపరచబడింది.",
            "detected_language": "te",
            "response_language": "te",
        },
    )
    response = client.post(
        path + "/messages", json={"content": "నా ప్రశ్నను భద్రపరచండి", "language": "en"}
    )
    assert response.status_code == 201
    turn = response.json()
    assert turn["user_message"]["detected_language"] == "te"
    assert turn["assistant_message"]["response_language"] == "te"
    assert client.get(path).json()["preferred_language"] == "en"
    with TestClient(create_app(settings)) as restarted:
        history = restarted.get(path + "/messages").json()
        assert history == [turn["user_message"], turn["assistant_message"]]


def test_read_only_context_can_read_chat_but_cannot_create_update_or_send(client):
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation_id"]
    read_only = demo_context("merchant_demo").with_updates(scopes=[Scope.TASKS_READ])
    client.app.dependency_overrides[current_context] = lambda: read_only
    path = f"/api/v1/conversations/{conversation_id}"
    assert client.get(path).status_code == 200
    assert client.get(path + "/messages").status_code == 200
    assert client.post("/api/v1/conversations", json={}).status_code == 403
    assert client.patch(path, json={"preferred_language": "te"}).status_code == 403
    assert client.post(path + "/messages", json={"content": "Blocked"}).status_code == 403
