from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from detour.voice.client import ElevenLabs, Speech, Transcript, VoiceError

LANG_CODE = {"en": "eng", "hi": "hin", "mr": "mar"}
FROM_CODE = {v: k for k, v in LANG_CODE.items()}


class VoiceService:
    """Speech with a disk cache and a spending cap. Everything here is safe to call without a key: it just says no."""

    def __init__(
        self,
        client: ElevenLabs | None,
        cache_dir: Path | None = None,
        budget_chars: int = 20_000,
        max_chars: int = 500,
        log: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        self.client = client
        self.cache_dir = cache_dir
        self.budget, self.max_chars = budget_chars, max_chars
        self._log = log or (lambda action, details: None)
        self.spent = 0  # characters sent for synthesis this run (cache hits cost nothing)
        self.hits = self.misses = self.errors = 0
        self._mem: dict[str, bytes] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self._balance: tuple[float, dict[str, int] | None] = (0.0, None)
        self._refreshing = False
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def _key(self, text: str, voice: str) -> str:
        assert self.client is not None
        return hashlib.sha256(f"{self.client.tts_model}|{voice}|{text}".encode()).hexdigest()

    def _read(self, key: str) -> bytes | None:
        if key in self._mem:
            return self._mem[key]
        if self.cache_dir and (p := self.cache_dir / f"{key}.mp3").exists():
            self._mem[key] = p.read_bytes()
            return self._mem[key]
        return None

    def cached(self, text: str, lang: str) -> bool:
        if not self.client:
            return False
        return self._read(self._key(text, self.client.voice_for(lang))) is not None

    def speak(self, text: str, lang: str) -> bytes:
        """Audio for `text`. Served from the cache when it has been said before."""
        if self.client is None:
            raise VoiceError("Voice is not set up.", "voice_off")
        if len(text) > self.max_chars:
            raise VoiceError("That message is too long to speak.", "voice_too_long")
        voice = self.client.voice_for(lang)
        key = self._key(text, voice)
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:  # two phones asking for the same sentence at once pay once
            if (audio := self._read(key)) is not None:
                self.hits += 1
                return audio
            with self._guard:
                if self.spent + len(text) > self.budget:
                    raise VoiceError("The voice budget for this run is used up.", "voice_budget")
            try:
                speech: Speech = self.client.tts(text, voice)
            except VoiceError:
                self.errors += 1
                raise
            with self._guard:
                self.spent += len(text)
                self.misses += 1
            self._mem[key] = speech.audio
            if self.cache_dir:
                (self.cache_dir / f"{key}.mp3").write_bytes(speech.audio)
            self._log("voice_generated", {"chars": len(text), "lang": lang, "credits": speech.cost, "key": key[:12]})
            return speech.audio

    def transcribe(self, audio: bytes, content_type: str) -> Transcript:
        if self.client is None:
            raise VoiceError("Voice is not set up.", "voice_off")
        try:
            return self.client.stt(
                audio, content_type, None
            )  # let it detect the language; the driver's choice is a hint only
        except VoiceError:
            self.errors += 1
            raise

    def _refresh_balance(self) -> None:
        try:
            assert self.client is not None
            self._balance = (time.time(), self.client.balance())
        finally:
            self._refreshing = False

    def status(self) -> dict[str, Any]:
        files = len(list(self.cache_dir.glob("*.mp3"))) if self.cache_dir else len(self._mem)
        out: dict[str, Any] = {
            "enabled": self.enabled,
            "tts_model": self.client.tts_model if self.client else None,
            "stt_model": self.client.stt_model if self.client else None,
            "budget": {"spent": self.spent, "limit": self.budget},
            "cache": {"files": files, "hits": self.hits, "misses": self.misses, "errors": self.errors},
            "account": None,
        }
        if self.client:
            ts, bal = self._balance
            if time.time() - ts > 60 and not self._refreshing:
                # never make the screen wait for ElevenLabs just to show a credit count
                self._refreshing = True
                threading.Thread(target=self._refresh_balance, daemon=True).start()
            out["account"] = bal
        return out


def from_env(
    env: dict[str, str], cache_dir: Path | None, log: Callable[[str, dict[str, Any]], None] | None = None
) -> VoiceService:
    """Voice from the environment. No key, or DETOUR_VOICE=off, gives a service that simply says it is off."""
    key = env.get("ELEVENLABS_API_KEY", "").strip()
    if not key or env.get("DETOUR_VOICE", "auto").lower() == "off":
        return VoiceService(None, cache_dir, log=log)
    voices = {lang: v for lang in ("en", "hi", "mr") if (v := env.get(f"ELEVENLABS_VOICE_{lang.upper()}", "").strip())}
    client = ElevenLabs(
        key,
        tts_model=env.get("ELEVENLABS_TTS_MODEL", "eleven_v4_turbo"),
        stt_model=env.get("ELEVENLABS_STT_MODEL", "scribe_v1"),
        default_voice=env.get("ELEVENLABS_VOICE_ID", "").strip() or "Xb7hH8MSUJpSbSDYk0k2",
        voices=voices,
    )
    return VoiceService(client, cache_dir, budget_chars=int(env.get("DETOUR_VOICE_BUDGET", "20000")), log=log)
