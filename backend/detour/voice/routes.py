from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, Request, Response

from detour.rescue.service import RescueService
from detour.session import ApiError, Session
from detour.voice.client import VoiceError
from detour.voice.service import FROM_CODE, VoiceService
from detour.voice.warm import warm


def with_ranges(data: bytes, range_header: str | None) -> Response:
    """Serve audio so a browser can ask for part of it. Safari will not play audio from a server that ignores this."""
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=86400"}
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", (range_header or "").strip())
    if not m or not (m[1] or m[2]):
        return Response(data, media_type="audio/mpeg", headers=headers)
    n = len(data)
    if m[1]:
        start, end = int(m[1]), min(int(m[2]) if m[2] else n - 1, n - 1)
    else:  # the last N bytes
        start, end = max(0, n - int(m[2])), n - 1
    if start >= n or start > end:
        return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{n}"})
    return Response(
        data[start : end + 1],
        status_code=206,
        media_type="audio/mpeg",
        headers={**headers, "Content-Range": f"bytes {start}-{end}/{n}"},
    )


MAX_AUDIO = 3_000_000  # about a minute of speech; a report is a few seconds


def build_router(s: Session, svc: RescueService, voice: VoiceService) -> APIRouter:
    r = APIRouter()

    @r.get("/voice/status")
    async def status() -> dict[str, Any]:
        return await asyncio.to_thread(voice.status)

    @r.get("/voice/audio")
    async def audio(request: Request, what: str, ref: str, lang: str = "en") -> Response:
        """Speak something the system itself produced, found by id. Free text is never spoken."""
        text = svc.speakable(what, ref, lang)
        try:
            data = await asyncio.to_thread(voice.speak, text, lang)
        except VoiceError as e:
            raise ApiError(503, e.code, e.message) from e
        return with_ranges(data, request.headers.get("range"))

    @r.post("/incidents/voice")
    async def voice_report(request: Request, driver: str, language: str | None = None) -> dict[str, Any]:
        """A driver's spoken report: audio in, transcript and the new incident out. The audio is not kept."""
        if int(request.headers.get("content-length") or 0) > MAX_AUDIO:
            raise ApiError(413, "audio_too_large", "That recording is too long. Keep it to a few seconds.")
        data = await request.body()
        if len(data) > MAX_AUDIO:
            raise ApiError(413, "audio_too_large", "That recording is too long. Keep it to a few seconds.")
        if len(data) < 800:
            raise ApiError(422, "nothing_heard", "I could not hear anything. Try again, or type it.")
        try:
            tr = await asyncio.to_thread(voice.transcribe, data, request.headers.get("content-type", ""))
        except VoiceError as e:
            raise ApiError(503, e.code, e.message) from e
        if not tr.text:
            raise ApiError(422, "nothing_heard", "I could not hear anything. Try again, or type it.")
        s.log(
            driver,
            "voice_transcribed",
            {
                "engine": "elevenlabs",
                "model": voice.client.stt_model if voice.client else None,
                "detected": tr.language,
                "chars": len(tr.text),
                "audio_bytes": len(data),
            },
        )
        inc = svc.report(driver, tr.text, language, None, None, "voice", engine="elevenlabs")
        return {
            "transcript": tr.text,
            "detected_language": FROM_CODE.get(tr.language or ""),
            "server_time": svc.wall(),
            "incident": svc.incident_view(inc),
        }

    @r.post("/voice/transcribe")
    async def transcribe(request: Request) -> dict[str, Any]:
        """Speech to text for anything a person says to the system. The audio is not kept."""
        data = await request.body()
        if len(data) > MAX_AUDIO:
            raise ApiError(413, "audio_too_large", "That recording is too long. Keep it to a few seconds.")
        if len(data) < 800:
            raise ApiError(422, "nothing_heard", "I could not hear anything. Try again, or type it.")
        try:
            tr = await asyncio.to_thread(voice.transcribe, data, request.headers.get("content-type", ""))
        except VoiceError as e:
            raise ApiError(503, e.code, e.message) from e
        if not tr.text:
            raise ApiError(422, "nothing_heard", "I could not hear anything. Try again, or type it.")
        s.log("voice", "voice_transcribed", {"engine": "elevenlabs", "chars": len(tr.text), "audio_bytes": len(data)})
        return {"transcript": tr.text, "detected_language": FROM_CODE.get(tr.language or "")}

    @r.post("/voice/warm")
    async def prepare(everyone: bool = False) -> dict[str, Any]:
        if not voice.enabled:
            raise ApiError(503, "voice_off", "Voice is not set up. Add ELEVENLABS_API_KEY to .env.")
        return await asyncio.to_thread(warm, voice, everyone)

    return r
