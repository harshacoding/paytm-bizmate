import asyncio
import base64
import contextlib
import json
from urllib.parse import urlencode

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from websockets.asyncio.client import connect

router = APIRouter()


class VoiceStatus(BaseModel):
    configured: bool


def api_key(settings) -> str:
    return settings.elevenlabs_api_key.get_secret_value() if settings.elevenlabs_api_key else ""


@router.get("/api/v1/voice/status", response_model=VoiceStatus, tags=["voice"])
def voice_status(request: Request):
    return VoiceStatus(configured=bool(api_key(request.app.state.settings)))


@router.websocket("/api/v1/voice/stream")
async def voice_stream(client: WebSocket):
    settings = client.app.state.settings
    if client.headers.get("origin") not in settings.cors_origins:
        await client.close(code=1008)
        return
    await client.accept()
    key = api_key(settings)
    if not key:
        await client.send_json({"message_type": "error", "code": "voice_not_configured"})
        await client.close(code=1013)
        return
    query = urlencode(
        {
            "model_id": "scribe_v3_live",
            "audio_format": "pcm_16000",
            "commit_strategy": "manual",
            "multilang_mode": "true",
            "secondary_languages": ["en", "hi", "te"],
        },
        doseq=True,
    )
    tasks = []
    try:
        async with connect(
            "wss://api.elevenlabs.io/v1/speech-to-text/realtime?" + query,
            additional_headers={"xi-api-key": key},
            open_timeout=20,
            max_size=1024 * 1024,
        ) as provider:

            async def send_audio():
                while True:
                    message = await client.receive_text()
                    if len(message) > 65536:
                        raise ValueError("Audio chunk too large")
                    data = json.loads(message)
                    audio = data.get("audio_base_64", "")
                    if data.get("message_type") != "input_audio_chunk" or not isinstance(
                        audio, str
                    ):
                        raise ValueError("Invalid audio message")
                    base64.b64decode(audio, validate=True)
                    await provider.send(
                        json.dumps(
                            {
                                "message_type": "input_audio_chunk",
                                "audio_base_64": audio,
                                "sample_rate": 16000,
                                "commit": data.get("commit") is True,
                            }
                        )
                    )

            async def receive_transcripts():
                async for message in provider:
                    data = json.loads(message)
                    kind = data.get("message_type", "")
                    if kind == "session_started":
                        await client.send_json({"message_type": kind})
                    elif kind in ("partial_transcript", "committed_transcript"):
                        await client.send_json({"message_type": kind, "text": data.get("text", "")})
                    elif "error" in kind:
                        raise RuntimeError("Speech provider unavailable")

            tasks = [asyncio.create_task(send_audio()), asyncio.create_task(receive_transcripts())]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
    except WebSocketDisconnect:
        pass
    except Exception:
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            await client.send_json({"message_type": "error", "code": "voice_unavailable"})
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            await client.close()
