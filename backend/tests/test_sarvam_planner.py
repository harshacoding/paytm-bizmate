import json
from io import BytesIO
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import bizmate.agents.planner as module
from bizmate.config import Settings
from bizmate.main import create_app


def goal(**changes):
    return {
        "intent": "settlement",
        "goal": "Investigate settlement",
        "detected_language": "te",
        "inactivity_days": 30,
        "offer_message": None,
        "needs_clarification": False,
        **changes,
    }


def reply(content=None, **choice):
    return BytesIO(
        json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(content or goal())},
                        **choice,
                    }
                ]
            }
        ).encode()
    )


@pytest.mark.parametrize(
    "provider,model,url,header",
    [
        (
            "sarvam",
            "sarvam-105b",
            "https://api.sarvam.ai/v1/chat/completions",
            "Api-subscription-key",
        ),
        ("openai", "gpt-4o-mini", "https://api.openai.com/v1/chat/completions", "Authorization"),
    ],
)
def test_correct_provider_model_credentials_and_strict_schema(
    monkeypatch, provider, model, url, header
):
    settings = Settings(
        _env_file=None,
        planner_mode=provider,
        sarvam_api_key=SecretStr("test-sarvam-key"),
        openai_api_key=SecretStr("test-openai-key"),
    )
    original = "  నా సెటిల్‌మెంట్ ఎందుకు తక్కువగా ఉంది?\n"

    def request(req, timeout):
        assert req.full_url == url and req.method == "POST" and timeout == 15
        expected = "test-sarvam-key" if provider == "sarvam" else "Bearer test-openai-key"
        assert req.get_header(header) == expected
        assert (
            req.get_header("Authorization" if provider == "sarvam" else "Api-subscription-key")
            is None
        )
        body = json.loads(req.data)
        assert body["model"] == model
        assert body["messages"][-1] == {"role": "user", "content": original}
        schema = body["response_format"]["json_schema"]
        assert schema["strict"] and schema["schema"]["additionalProperties"] is False
        assert set(schema["schema"]["required"]) == set(module.GoalExtraction.model_fields)
        assert "test-sarvam-key" not in json.dumps(body)
        if provider == "sarvam":
            # V1 accepts JSON null to disable reasoning; the string "none" returns HTTP 400.
            assert body["reasoning_effort"] is None
            assert body["max_tokens"] == 4096
        return reply()

    monkeypatch.setattr(module, "urlopen", request)
    result = module.Planner(settings).invoke({"request": original, "preferred_language": "en"})
    assert result["intent"] == "settlement" and result["response_language"] == "te"
    assert "planner_error" not in result


def test_sarvam_model_can_be_configured(monkeypatch):
    settings = Settings(
        _env_file=None,
        planner_mode="sarvam",
        planner_model="sarvam-105b-conversations",
        sarvam_api_key=SecretStr("test-key"),
    )

    def request(req, timeout):
        assert json.loads(req.data)["model"] == "sarvam-105b-conversations"
        return reply()

    monkeypatch.setattr(module, "urlopen", request)
    assert module.Planner(settings).extract("settlement").intent == "settlement"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_sarvam_key_never_uses_openai_credentials(monkeypatch, value):
    settings = Settings(
        _env_file=None,
        planner_mode="sarvam",
        sarvam_api_key=SecretStr(value) if value is not None else None,
        openai_api_key=SecretStr("private-openai-key"),
    )

    def unexpected(*args, **kwargs):
        pytest.fail("No provider request should be made without its selected key")

    monkeypatch.setattr(module, "urlopen", unexpected)
    result = module.Planner(settings).invoke({"request": "Why is my settlement short?"})
    assert result["intent"] == "unknown" and result["planner_error"]
    assert "private-openai-key" not in json.dumps(result)


@pytest.mark.parametrize("status", [400, 403, 429, 500])
def test_sarvam_provider_errors_fail_closed_without_leaking_credentials(monkeypatch, status):
    settings = Settings(
        _env_file=None, planner_mode="sarvam", sarvam_api_key=SecretStr("private-key")
    )

    def request(*args, **kwargs):
        raise HTTPError(
            "https://api.sarvam.ai/v1/chat/completions", status, "private-key", {}, None
        )

    monkeypatch.setattr(module, "urlopen", request)
    result = module.Planner(settings).invoke({"request": "నా సెటిల్‌మెంట్ ఎందుకు తక్కువగా ఉంది?"})
    assert result["intent"] == "unknown" and result["needs_clarification"]
    assert result["response_language"] == "te" and "private-key" not in json.dumps(result)


@pytest.mark.parametrize(
    "failure",
    ["timeout", "identity", "tools", "invalid_json", "truncated", "refusal", "no_choices"],
)
def test_untrusted_or_incomplete_sarvam_output_cannot_become_an_action(monkeypatch, failure):
    settings = Settings(_env_file=None, planner_mode="sarvam", sarvam_api_key=SecretStr("test-key"))

    def request(*args, **kwargs):
        if failure == "timeout":
            raise TimeoutError("test-key")
        if failure == "identity":
            return reply(goal(merchant_id="merchant_other"))
        if failure == "tools":
            return reply({"tool": "send_campaign", "approved": True})
        if failure == "truncated":
            return reply(finish_reason="length")
        if failure == "refusal":
            return reply(message={"content": None, "refusal": "test-key"})
        if failure == "no_choices":
            return BytesIO(b'{"choices":[]}')
        return BytesIO(b'{"choices":[{"message":{"content":"not JSON"}}]}')

    monkeypatch.setattr(module, "urlopen", request)
    result = module.Planner(settings).invoke({"request": "Why is my settlement short?"})
    assert result["intent"] == "unknown" and result["planner_error"]
    assert "test-key" not in json.dumps(result)


def test_sarvam_environment_and_secret_redaction(tmp_path, monkeypatch):
    monkeypatch.delenv("BIZMATE_PLANNER_MODE", raising=False)
    monkeypatch.delenv("BIZMATE_SARVAM_API_KEY", raising=False)
    env = tmp_path / "sarvam.env"
    env.write_text(
        "BIZMATE_PLANNER_MODE=sarvam\nBIZMATE_SARVAM_API_KEY=private-env-key\n", encoding="utf-8"
    )
    settings = Settings(_env_file=env)
    assert (
        settings.planner_mode == "sarvam"
        and settings.sarvam_api_key.get_secret_value() == "private-env-key"
    )
    assert "private-env-key" not in repr(settings)


def test_sarvam_agent_intake_still_stops_for_merchant_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: reply())
    settings = Settings(
        _env_file=None,
        database_path=str(tmp_path / "sarvam.sqlite3"),
        planner_mode="sarvam",
        sarvam_api_key=SecretStr("test-key"),
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/tasks", json={"message": "నా సెటిల్‌మెంట్ ఎందుకు తక్కువగా ఉంది?"})
        assert response.status_code == 201, response.text
        task = response.json()
        assert task["status"] == "AWAITING_APPROVAL" and task["intent"] == "settlement"
        assert task["workflow_data"]["response_language"] == "te"
        assert task["approvals"][0]["decision"] == "pending"
        assert not task["receipts"] and not task["verifications"]


@pytest.mark.parametrize("intent", ["unknown", "settlement"])
def test_sarvam_chat_reply_cannot_replace_workflow_evidence(monkeypatch, tmp_path, intent):
    answer = "A settlement transfers collected payments after deductions."
    content = goal(intent=intent, detected_language="en", reply=answer)
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: reply(content))
    settings = Settings(
        _env_file=None,
        database_path=str(tmp_path / "chat.sqlite3"),
        planner_mode="sarvam",
        sarvam_api_key=SecretStr("test-key"),
    )
    with TestClient(create_app(settings)) as client:
        conversation = client.post("/api/v1/conversations", json={}).json()
        turn = client.post(
            f"/api/v1/conversations/{conversation['conversation_id']}/messages",
            json={
                "content": "What is settlement?"
                if intent == "unknown"
                else "Why is my settlement short?"
            },
        ).json()
        message = turn["assistant_message"]
        if intent == "unknown":
            assert message["content"] == answer and message["task_id"] is None
        else:
            assert "166.80" in message["content"] and message["content"] != answer
            assert message["task_id"]
