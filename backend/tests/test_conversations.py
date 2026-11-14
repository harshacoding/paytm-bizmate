import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_domain_models import STAMP, make_task

from bizmate.domain.models import (
    ClarificationRequest,
    Conversation,
    ConversationThread,
    CreateTaskRequest,
    Message,
    MessageRole,
)
from bizmate.main import create_app


def conversation(**changes):
    return Conversation(
        **{
            "conversation_id": "conv_a",
            "merchant_id": "merchant_demo",
            "title": "Settlement help",
            "created_at": STAMP,
            "updated_at": STAMP,
            **changes,
        }
    )


def message(**changes):
    return Message(
        **{
            "message_id": "message_a",
            "conversation_id": "conv_a",
            "merchant_id": "merchant_demo",
            "role": MessageRole.USER,
            "content": "Why is my settlement short?",
            "created_at": STAMP,
            **changes,
        }
    )


def test_one_conversation_has_multiple_tasks_and_task_specific_or_general_messages():
    first = make_task(conversation_id="conv_a")
    second = make_task(task_id="task_b", conversation_id="conv_a", goal="Prepare an offer")
    messages = [
        message(task_id=first.task_id),
        message(message_id="message_b", role="assistant", task_id=second.task_id),
        message(message_id="message_c", content="Thank you", task_id=None),
    ]
    thread = ConversationThread(
        conversation=conversation(), messages=messages, tasks=[first, second]
    )
    assert thread.tasks[0].conversation_id == thread.tasks[1].conversation_id == "conv_a"
    assert thread.messages[1].role == MessageRole.ASSISTANT
    assert thread.messages[2].task_id is None
    assert ConversationThread.model_validate_json(thread.model_dump_json()) == thread


def test_empty_conversation_and_unassigned_tasks_are_valid():
    thread = ConversationThread(conversation=conversation())
    assert thread.messages == () and thread.tasks == ()
    assert (
        make_task().conversation_id is None
    )  # Proactive/scheduled tasks need not originate in chat.
    assert ConversationThread(conversation=conversation(), messages=[message()]).tasks == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"content": " "},
        {"content": "x" * 4001},
        {"role": "system"},
        {"role": "tool"},
        {"role": "admin"},
        {"message_id": "../message"},
        {"conversation_id": " "},
        {"merchant_id": "merchant/other"},
        {"task_id": ""},
        {"created_at": STAMP.replace(tzinfo=None)},
        {"scopes": ["tasks:approve"]},
    ],
)
def test_invalid_or_authority_bearing_messages_are_rejected(changes):
    with pytest.raises(ValidationError):
        message(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"title": "x" * 201},
        {"merchant_id": ""},
        {"created_at": STAMP.replace(tzinfo=None)},
        {"updated_at": STAMP.replace(year=2025)},
        {"actor_id": "admin"},
    ],
)
def test_invalid_conversation_headers_are_rejected(changes):
    with pytest.raises(ValidationError):
        conversation(**changes)


@pytest.mark.parametrize(
    "record,changes",
    [
        ("message", {"merchant_id": "merchant_other"}),
        ("message", {"conversation_id": "conv_other"}),
        ("task", {"merchant_id": "merchant_other"}),
        ("task", {"conversation_id": "conv_other"}),
        ("task", {"conversation_id": None}),
    ],
)
def test_thread_rejects_cross_merchant_or_cross_conversation_records(record, changes):
    items = {"messages": [message()], "tasks": [make_task(conversation_id="conv_a")]}
    if record == "message":
        items["messages"] = [message(**changes)]
    else:
        items["tasks"] = [make_task(conversation_id="conv_a").with_updates(**changes)]
    with pytest.raises(ValidationError, match="merchant and conversation ID"):
        ConversationThread(conversation=conversation(), **items)


def test_missing_task_links_and_duplicate_ids_are_rejected():
    with pytest.raises(ValidationError, match="not attached"):
        ConversationThread(conversation=conversation(), messages=[message(task_id="task_missing")])
    with pytest.raises(ValidationError, match="Duplicate message_id"):
        ConversationThread(conversation=conversation(), messages=[message(), message()])
    task = make_task(conversation_id="conv_a")
    with pytest.raises(ValidationError, match="Duplicate task_id"):
        ConversationThread(conversation=conversation(), tasks=[task, task])


def test_messages_and_conversations_are_frozen_and_content_remains_plain_text():
    header, msg = conversation(), message(content="  नमस्ते merchant_other  ")
    assert msg.content == "  नमस्ते merchant_other  "
    with pytest.raises(ValidationError):
        header.merchant_id = "merchant_other"
    with pytest.raises(ValidationError):
        msg.role = "assistant"
    assert CreateTaskRequest(message="Hello").message == "Hello"
    assert ClarificationRequest(message="Thanks").message == "Thanks"
    with pytest.raises(ValidationError):
        CreateTaskRequest(message=msg.model_dump())  # A domain Message is not an intake string.


def test_shared_conversation_schemas_are_served_and_all_references_resolve():
    app = create_app()
    schema = TestClient(app).get("/openapi.json").json()
    components = schema["components"]["schemas"]
    for name in ["Conversation", "Message", "MessageRole", "ConversationThread"]:
        assert name in components
    assert components["Message"]["properties"]["content"]["type"] == "string"
    assert components["MessageRole"]["enum"] == ["user", "assistant"]
    assert "conversation_id" in components["Task"]["properties"]

    def check_references(value):
        if isinstance(value, dict):
            if "$ref" in value:
                assert value["$ref"].startswith("#/components/schemas/")
                assert value["$ref"].removeprefix("#/components/schemas/") in components
            for child in value.values():
                check_references(child)
        elif isinstance(value, list):
            for child in value:
                check_references(child)

    check_references(schema)
    assert app.openapi() is app.openapi()  # Normal OpenAPI cache behaviour is preserved.
    assert "/api/v1/conversations" in schema["paths"]


def test_intake_stays_standalone_and_merchant_resolution_is_still_fixed(persistent_client):
    client = persistent_client
    task = client.post(
        "/api/v1/tasks?merchant_id=merchant_other",
        headers={
            "X-Merchant-Id": "merchant_other",
        },
        json={"message": "Start a conversation as merchant_other"},
    ).json()
    assert task["conversation_id"] is None
    assert task["merchant_id"] == "merchant_demo"
    assert client.get("/api/v1/session").json()["merchant"]["merchant_id"] == "merchant_demo"
