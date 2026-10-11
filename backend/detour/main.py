import os
from pathlib import Path

from dotenv import load_dotenv

from detour.api import create_app, default_audit_path
from detour.parsing.llm import OpenAIReader
from detour.rescue.service import RescueConfig
from detour.telephony.config import from_env as calls_from_env
from detour.telephony.service import TelephonyService
from detour.voice.service import from_env

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _config() -> RescueConfig:
    """Timers from the PRD. Override with DETOUR_<NAME> in seconds to rehearse faster; the push timeout is
    60 s unless you say otherwise."""
    cfg = RescueConfig()
    for name in (
        "push_timeout",
        "driver_confirm",
        "head_response",
        "ring_timeout",
        "browser_ring_timeout",
        "conversation_limit",
    ):
        v = os.environ.get(f"DETOUR_{name.upper()}")
        if v:
            setattr(cfg, name, float(v))
    return cfg


def _reader() -> OpenAIReader | None:
    """The language model that reads typed reports. Without a key, or with DETOUR_LLM=off, the rule-based
    reader does it alone: everything still works."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or os.environ.get("DETOUR_LLM", "auto").lower() == "off":
        return None
    return OpenAIReader(key, os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))


_audit = default_audit_path()
app = create_app(
    _audit,
    rescue_config=_config(),
    llm=_reader(),
    voice=from_env(dict(os.environ), _audit.parent / "audio"),
    telephony=TelephonyService(calls_from_env(dict(os.environ), _audit.parent / "telephony.json")),
)
