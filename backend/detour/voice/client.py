from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger("detour.voice")
BASE = "https://api.elevenlabs.io"
EXTENSIONS = {
    "webm": "webm",
    "ogg": "ogg",
    "mp4": "m4a",
    "m4a": "m4a",
    "aac": "aac",
    "wav": "wav",
    "mpeg": "mp3",
    "mp3": "mp3",
}


class VoiceError(Exception):
    """Voice could not be used right now. The caller falls back to the browser's voice, or to typing."""

    def __init__(self, message: str, code: str = "voice_unavailable"):
        super().__init__(message)
        self.message, self.code = message, code


@dataclass
class Speech:
    audio: bytes
    cost: int | None  # credits ElevenLabs says it charged, when it says


@dataclass
class Transcript:
    text: str
    language: str | None  # ISO 639-3 as ElevenLabs reports it: eng, hin, mar


class ElevenLabs:
    def __init__(
        self,
        api_key: str,
        *,
        tts_model: str = "eleven_v4_turbo",
        stt_model: str = "scribe_v1",
        default_voice: str = "Xb7hH8MSUJpSbSDYk0k2",  # "Alice": a clear premade voice that reads Hindi and Marathi well
        voices: dict[str, str] | None = None,
        timeout: float = 25.0,
        http: httpx.Client | None = None,
    ):
        self.tts_model, self.stt_model = tts_model, stt_model
        self.default_voice = default_voice
        self.voices = voices or {}
        self._http = http or httpx.Client(timeout=timeout)
        self._headers = {"xi-api-key": api_key}

    def voice_for(self, lang: str) -> str:
        return self.voices.get(lang) or self.default_voice

    def _fail(self, what: str, r: httpx.Response) -> VoiceError:
        log.warning("elevenlabs %s failed: %s", what, r.status_code)
        if r.status_code in (401, 403):
            return VoiceError("ElevenLabs refused the key.", "voice_key_refused")
        if r.status_code == 429 or "quota" in r.text.lower():
            return VoiceError("The ElevenLabs credit or rate limit was reached.", "voice_quota")
        return VoiceError(f"ElevenLabs could not do that (status {r.status_code}).")

    def tts(self, text: str, voice_id: str) -> Speech:
        try:
            r = self._http.post(
                f"{BASE}/v1/text-to-speech/{voice_id}",
                params={"output_format": "mp3_44100_64"},
                headers={**self._headers, "Content-Type": "application/json"},
                json={"text": text, "model_id": self.tts_model},
            )
        except httpx.HTTPError as e:
            log.warning("elevenlabs tts network error: %s", type(e).__name__)
            raise VoiceError("Could not reach ElevenLabs.") from e
        if r.status_code != 200:
            raise self._fail("tts", r)
        cost = r.headers.get("character-cost")
        return Speech(r.content, int(cost) if cost and cost.isdigit() else None)

    def stt(self, audio: bytes, content_type: str, language: str | None = None) -> Transcript:
        data = {"model_id": self.stt_model}
        if language:
            data["language_code"] = language
        base = (content_type or "").split(";")[0].strip().lower()
        ext = next((e for k, e in EXTENSIONS.items() if k in base), "bin")  # phones send webm, ogg or mp4/m4a
        try:
            r = self._http.post(
                f"{BASE}/v1/speech-to-text",
                headers=self._headers,
                data=data,
                files={"file": (f"report.{ext}", audio, base or "application/octet-stream")},
            )
        except httpx.HTTPError as e:
            log.warning("elevenlabs stt network error: %s", type(e).__name__)
            raise VoiceError("Could not reach ElevenLabs.") from e
        if r.status_code != 200:
            raise self._fail("stt", r)
        j = r.json()
        return Transcript((j.get("text") or "").strip(), j.get("language_code"))

    def balance(self) -> dict[str, int] | None:
        """Credits used and available, best effort. The counter updates a few seconds late."""
        try:
            r = self._http.get(f"{BASE}/v1/user/subscription", headers=self._headers, timeout=5)
            if r.status_code == 200:
                j = r.json()
                return {"used": int(j["character_count"]), "limit": int(j["character_limit"])}
        except (httpx.HTTPError, KeyError, ValueError):
            pass
        return None
