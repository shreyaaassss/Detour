from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def read_state(path: Path | None) -> dict[str, Any]:
    if path and path.exists():
        try:
            return json.loads(path.read_text())
        except ValueError:
            return {}
    return {}


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))
    path.chmod(0o600)  # it holds the shared secret


def mask(number: str) -> str:
    """+91******210: enough to recognise, not enough to copy."""
    return number[:3] + "*" * max(0, len(number) - 6) + number[-3:] if len(number) > 6 else "***"


@dataclass
class CallSettings:
    enabled: bool = False
    api_key: str = ""
    agent_id: str | None = None
    phone_number_id: str | None = None
    phones: dict[str, str] = field(default_factory=dict)  # a driver's name in lower case, or "*" for everyone
    language: str = "hi"  # the language of the call: hi, mr, en, or "driver" to follow the driver's own
    public_url: str | None = None
    secret: str | None = None
    max_calls: int = 6  # per run, so a mistake cannot ring someone over and over
    agent_name: str = "DeTour rescue call"
    bad_numbers: list[str] = field(default_factory=list)  # names (never values) of PHONE_ settings that are malformed

    def phone_for(self, driver: str | None) -> str | None:
        return self.phones.get((driver or "").casefold()) or self.phones.get("*")

    def missing(self) -> list[str]:
        out = []
        if not self.enabled:
            out.append("DETOUR_CALLS=on")
        if not self.api_key:
            out.append("ELEVENLABS_API_KEY")
        if not self.agent_id:
            out.append("the call agent (run: uv run python -m detour.telephony.setup)")
        if not self.phone_number_id:
            out.append("ELEVENLABS_PHONE_NUMBER_ID (connect a phone number in ElevenLabs)")
        if self.bad_numbers:
            out.append(f"{', '.join(self.bad_numbers)} in international format, like +919876543210")
        elif not self.phones:
            out.append("a number to call (PHONE_RESCUE_DRIVER)")
        return out


def from_env(env: dict[str, str], state_path: Path | None = None) -> CallSettings:
    state = read_state(state_path)
    phones: dict[str, str] = {}
    bad: list[str] = []
    for k, v in env.items():
        if not k.startswith("PHONE_") or k in ("PHONE_HEAD", "PHONE_STRANDED_DRIVER") or not v.strip():
            continue
        number = re.sub(
            r"[ \-().]", "", v.strip()
        )  # forgive spaces, dashes and brackets, but never guess a country code
        if not E164.match(number):
            bad.append(k)
        elif k == "PHONE_RESCUE_DRIVER":
            phones["*"] = number
        else:
            phones[k[6:].casefold()] = number
    return CallSettings(
        enabled=env.get("DETOUR_CALLS", "off").lower() == "on",
        api_key=env.get("ELEVENLABS_API_KEY", "").strip(),
        agent_id=env.get("ELEVENLABS_AGENT_ID", "").strip() or state.get("agent_id"),
        phone_number_id=env.get("ELEVENLABS_PHONE_NUMBER_ID", "").strip() or None,
        phones=phones,
        language=env.get("DETOUR_CALL_LANGUAGE", "hi").strip().lower(),
        public_url=(env.get("PUBLIC_BASE_URL", "").strip().rstrip("/") or None),
        secret=env.get("DETOUR_AGENT_SECRET", "").strip() or state.get("secret"),
        max_calls=int(env.get("DETOUR_MAX_CALLS", "6")),
        bad_numbers=bad,
    )
