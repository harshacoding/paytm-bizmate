import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
from test_conversations import conversation, message
from test_domain_models import make_task

from bizmate.domain.models import (
    ClarificationRequest,
    LanguageCode,
    LanguageContext,
    Merchant,
    Message,
)
from bizmate.domain.types import MessageText
from bizmate.main import create_app
from bizmate.services.demo import demo_context


@pytest.mark.parametrize("code", ["en", "te", "hi"])
def test_supported_languages_roundtrip_in_all_contracts(code):
    merchant = Merchant(merchant_id="m", display_name="Store", scopes=[], preferred_language=code)
    header = conversation(preferred_language=code)
    msg = message(detected_language=code, response_language=code)
    language = LanguageContext(
        preferred_language=code, detected_language=code, response_language=code
    )
    for record in [merchant, header, msg, language]:
        assert type(record).model_validate_json(record.model_dump_json()) == record
    assert merchant.model_dump(mode="json")["preferred_language"] == code
    assert (
        demo_context("merchant_demo")
        .with_updates(
            preferred_language=code,
        )
        .public_merchant()
        .preferred_language
        == code
    )


@pytest.mark.parametrize("code", ["fr", "en-US", "te-IN", "EN", "auto", "", " en ", 1, False])
def test_unsupported_codes_are_rejected_everywhere(code):
    for build in [
        lambda: Merchant(merchant_id="m", display_name="Store", scopes=[], preferred_language=code),
        lambda: conversation(preferred_language=code),
        lambda: message(detected_language=code),
        lambda: message(response_language=code),
        lambda: LanguageContext(preferred_language=code),
        lambda: LanguageContext(detected_language=code),
        lambda: LanguageContext(response_language=code),
    ]:
        with pytest.raises(ValidationError):
            build()


def test_language_defaults_do_not_invent_detection_or_response_metadata():
    merchant = Merchant(merchant_id="m", display_name="Store", scopes=[])
    assert merchant.preferred_language == LanguageCode.ENGLISH
    assert conversation().preferred_language == LanguageCode.ENGLISH
    assert LanguageContext().model_dump(mode="json") == {
        "preferred_language": "en",
        "detected_language": None,
        "response_language": None,
    }
    assert message().detected_language is None and message().response_language is None
    assert (
        LanguageContext(
            preferred_language="te", detected_language="hi", response_language="te"
        ).response_language
        == LanguageCode.TELUGU
    )
    with pytest.raises(ValidationError):
        LanguageContext(preferred_language=None)
    with pytest.raises(ValidationError):
        conversation(preferred_language=None)


@pytest.mark.parametrize(
    "content",
    [
        "  Why is my settlement short?\n\t",
        "  నా సెటిల్‌మెంట్ ఎందుకు తక్కువగా వచ్చింది?\r\n\t",
        "\t मेरी राशि कम क्यों है?  \n",
        "  తెలుగు + हिन्दी + English e\u0301 🙂\r\n",
    ],
)
def test_original_content_is_preserved_when_language_metadata_changes(content):
    original = message(content=content)
    updated = original.with_updates(detected_language="hi", response_language="te")
    assert original.content == updated.content == content
    assert Message.model_validate_json(updated.model_dump_json()).content == content
    assert make_task(original_request=content).original_request == content
    assert ClarificationRequest(message=content).message == content


@pytest.mark.parametrize("content", ["", " ", "\t\r\n", "\u2003\u3000", "x" * 4001, b"text"])
def test_original_message_validation_rejects_blank_oversize_and_non_string_input(content):
    with pytest.raises(ValidationError):
        TypeAdapter(MessageText).validate_python(content)


def test_length_limit_applies_to_original_content_before_any_normalization():
    content = " " + "అ" * 3998 + " "
    assert TypeAdapter(MessageText).validate_python(content) == content
    with pytest.raises(ValidationError):
        TypeAdapter(MessageText).validate_python(content + " ")


def test_task_intake_and_follow_up_preserve_original_content_and_fixed_identity():
    client = TestClient(create_app())
    content = "  తెలుగు / हिन्दी / English\n\t"
    response = client.post(
        "/api/v1/tasks?preferred_language=hi&merchant_id=merchant_other", json={"message": content}
    )
    assert response.status_code == 201
    task = response.json()
    assert task["original_request"] == content
    assert task["conversation_id"] is None and task["merchant_id"] == "merchant_demo"
    follow_up = "\t ధన్యవాదాలు / धन्यवाद  \n"
    updated = client.post(
        f"/api/v1/tasks/{task['task_id']}/messages", json={"message": follow_up}
    ).json()
    assert updated["events"][-1]["message"] == follow_up
    saved = client.get(f"/api/v1/tasks/{task['task_id']}").json()
    assert saved["original_request"] == content
    assert saved["events"][-1]["message"] == follow_up
    session = client.get("/api/v1/session").json()
    assert session["merchant"]["preferred_language"] == "en"
    assert session["merchant"]["merchant_id"] == "merchant_demo"


@pytest.mark.parametrize("content", [" " * 100 + "Explain my settlement", " " * 3999 + "అ"])
def test_valid_leading_whitespace_cannot_create_an_empty_task_title(content):
    client = TestClient(create_app())
    response = client.post("/api/v1/tasks", json={"message": content})
    assert response.status_code == 201
    assert response.json()["goal"] == content.strip()[:90]
    assert response.json()["original_request"] == content


def test_language_models_are_frozen_and_task_conversation_link_remains_optional():
    language = LanguageContext(preferred_language="te")
    with pytest.raises(ValidationError):
        language.preferred_language = "hi"
    with pytest.raises(ValidationError):
        LanguageContext(scopes=["tasks:approve"])
    assert make_task().conversation_id is None
    assert make_task(conversation_id="conversation_a").conversation_id == "conversation_a"


def test_openapi_exposes_language_metadata_with_only_supported_codes():
    schema = create_app().openapi()["components"]["schemas"]
    assert schema["LanguageCode"]["enum"] == ["en", "te", "hi"]
    assert "LanguageContext" in schema
    assert "preferred_language" in schema["Merchant"]["properties"]
    assert "preferred_language" in schema["Conversation"]["properties"]
    assert "detected_language" in schema["Message"]["properties"]
    assert "response_language" in schema["Message"]["properties"]
    assert "conversation_id" in schema["Task"]["properties"]
