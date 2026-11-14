import asyncio
import base64
import json
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from pydantic import SecretStr

from bizmate.config import Settings
from bizmate.main import create_app

ORIGIN = {"origin": "http://127.0.0.1:5173"}


def test_voice_requires_server_configuration_without_exposing_keys():
    client = TestClient(create_app(Settings(_env_file=None, elevenlabs_api_key=None)))
    assert client.get("/api/v1/voice/status").json() == {"configured": False}
    with client.websocket_connect("/api/v1/voice/stream", headers=ORIGIN) as socket:
        assert socket.receive_json() == {
            "message_type": "error",
            "code": "voice_not_configured",
        }


@pytest.mark.parametrize("_attempt", range(10))
def test_voice_stream_auto_detects_and_relays_partial_and_final_text(monkeypatch, _attempt):
    calls = []
    relay_tasks = set()
    relays_done_at_provider_exit = []

    class Provider:
        def __init__(self):
            self.events = asyncio.Queue()
            self.events.put_nowait(json.dumps({"message_type": "session_started"}))

        def __aiter__(self):
            return self

        async def __anext__(self):
            relay_tasks.add(asyncio.current_task())
            return await self.events.get()

        async def send(self, message):
            relay_tasks.add(asyncio.current_task())
            data = json.loads(message)
            kind = "committed_transcript" if data["commit"] else "partial_transcript"
            await self.events.put(json.dumps({"message_type": kind, "text": "నా చెల్లింపు"}))

    @asynccontextmanager
    async def fake_connect(url, **kwargs):
        calls.append((url, kwargs))
        try:
            yield Provider()
        finally:
            relays_done_at_provider_exit.append(all(task.done() for task in relay_tasks))

    monkeypatch.setattr("bizmate.api.voice.connect", fake_connect)
    settings = Settings(_env_file=None, elevenlabs_api_key=SecretStr("test-only-placeholder"))
    client = TestClient(create_app(settings))
    assert client.get("/api/v1/voice/status").json() == {"configured": True}
    with client.websocket_connect("/api/v1/voice/stream", headers=ORIGIN) as socket:
        assert socket.receive_json()["message_type"] == "session_started"
        socket.send_json(
            {
                "message_type": "input_audio_chunk",
                "audio_base_64": base64.b64encode(bytes(3200)).decode(),
                "commit": False,
            }
        )
        assert socket.receive_json() == {
            "message_type": "partial_transcript",
            "text": "నా చెల్లింపు",
        }
        socket.send_json({"message_type": "input_audio_chunk", "audio_base_64": "", "commit": True})
        assert socket.receive_json()["message_type"] == "committed_transcript"
    assert len(relay_tasks) == 2
    assert relays_done_at_provider_exit == [True]
    query = parse_qs(urlparse(calls[0][0]).query)
    assert "language_code" not in query
    assert query["secondary_languages"] == ["en", "hi", "te"]
    assert query["multilang_mode"] == ["true"]
    assert calls[0][1]["additional_headers"] == {"xi-api-key": "test-only-placeholder"}


@pytest.mark.parametrize(
    "ending", ["provider_error", "invalid_audio", "provider_eof", "idle_disconnect"]
)
def test_voice_relays_are_joined_before_provider_closes(monkeypatch, ending):
    relay_tasks = set()
    closed = []

    class Provider:
        def __init__(self):
            self.events = asyncio.Queue()
            self.events.put_nowait(json.dumps({"message_type": "session_started"}))

        def __aiter__(self):
            return self

        async def __anext__(self):
            relay_tasks.add(asyncio.current_task())
            event = await self.events.get()
            if event is None:
                raise StopAsyncIteration
            return event

        async def send(self, _message):
            relay_tasks.add(asyncio.current_task())
            if ending == "provider_eof":
                await self.events.put(None)
            else:
                await self.events.put(
                    json.dumps({"message_type": "auth_error", "detail": "private provider data"})
                )

    @asynccontextmanager
    async def fake_connect(*_args, **_kwargs):
        try:
            yield Provider()
        finally:
            closed.append(all(task.done() for task in relay_tasks))

    monkeypatch.setattr("bizmate.api.voice.connect", fake_connect)
    client = TestClient(
        create_app(Settings(_env_file=None, elevenlabs_api_key=SecretStr("test-only-placeholder")))
    )
    with client.websocket_connect("/api/v1/voice/stream", headers=ORIGIN) as socket:
        assert socket.receive_json() == {"message_type": "session_started"}
        if ending != "idle_disconnect":
            socket.send_json(
                {
                    "message_type": "input_audio_chunk",
                    "audio_base_64": "not base64!" if ending == "invalid_audio" else "",
                }
            )
            if ending != "provider_eof":
                assert socket.receive_json() == {
                    "message_type": "error",
                    "code": "voice_unavailable",
                }
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()
    assert relay_tasks
    assert closed == [True]
