"""Pre-generate the demo's voice lines, so the live demo is fast and spends nothing.

The lines are found by running the PRD story on a throwaway copy of the system, so they are exactly the sentences
the real flow will produce. A test checks this, because a line that differs by one word is a cache miss.
"""

from __future__ import annotations

from typing import Any

from detour.audit import AuditLog
from detour.events import EventBus
from detour.rescue.clock import SimClock
from detour.rescue.service import RescueConfig, RescueService
from detour.session import Session
from detour.voice.client import VoiceError
from detour.voice.service import VoiceService


class _Wall:
    t = 1_000_000.0

    def __call__(self) -> float:
        return self.t


def _sandbox() -> tuple[Session, RescueService]:
    wall = _Wall()
    session = Session(AuditLog(None), EventBus(), SimClock(wall=wall), None)
    svc = RescueService(session, RescueConfig(), wall=wall)
    session.reset_demo("warm")
    return session, svc


def demo_lines(everyone: bool = False) -> list[dict[str, str]]:
    """Every sentence the demo story says out loud: {label, lang, text}. `everyone` adds all three languages."""
    out: list[dict[str, str]] = []

    def add(label: str, text: dict[str, str] | None, lang: str) -> None:
        langs = ("en", "hi", "mr") if everyone else (lang,)
        for lg in langs:
            if text and lg in text and not any(o["text"] == text[lg] and o["lang"] == lg for o in out):
                out.append({"label": label, "lang": lg, "text": text[lg]})

    session, svc = _sandbox()
    inc = svc.report("Ravi", "My truck broke down near Hadapsar and I can't make the 3 PM delivery.")
    add("Read-back to the stranded driver", inc.readback, inc.language)
    svc.confirm(inc.id, True)
    add("Request sent", next(n.text for n in svc.notes if n.kind == "awaiting"), inc.language)
    prop = svc.incidents[inc.id].proposal
    assert prop is not None
    shortlist = [c.vehicle_id for c in prop.feasible][:3]
    svc.approve(inc.id, "head", shortlist, prop.plan_version)
    for _ in shortlist:
        offer = next(o for o in svc.offers.values() if o.status == "open")
        add(f"Offer to {offer.driver}", offer.text, offer.language)
        svc.respond(offer.id, "decline")
    add("Nobody can rescue", next(n.text for n in svc.notes if n.kind == "no_rescue"), inc.language)

    session, svc = _sandbox()
    inc = svc.report("Ravi", "My truck broke down near Hadapsar and I can't make the 3 PM delivery.")
    svc.confirm(inc.id, True)
    prop = svc.incidents[inc.id].proposal
    assert prop is not None
    svc.approve(inc.id, "head", [c.vehicle_id for c in prop.feasible][:3], prop.plan_version)
    offer = next(o for o in svc.offers.values() if o.status == "open")
    svc.respond(offer.id, "accept")
    add("Help is on the way", next(n.text for n in svc.notes if n.kind == "on_the_way"), inc.language)
    add(f"Thanks to {offer.driver}", next(n.text for n in svc.notes if n.kind == "confirmed"), offer.language)
    return out


def warm(voice: VoiceService, everyone: bool = False) -> dict[str, Any]:
    """Generate (or find in the cache) every demo line. Returns what was spent."""
    lines = demo_lines(everyone)
    new = cached = chars = 0
    problems: list[str] = []
    for ln in lines:
        had = voice.cached(ln["text"], ln["lang"])
        try:
            voice.speak(ln["text"], ln["lang"])
        except VoiceError as e:
            problems.append(f"{ln['label']} ({ln['lang']}): {e.message}")
            continue
        if had:
            cached += 1
        else:
            new += 1
            chars += len(ln["text"])
    return {"lines": len(lines), "generated": new, "already_cached": cached, "characters": chars, "problems": problems}


if __name__ == "__main__":  # uv run python -m detour.voice.warm
    import os
    from pathlib import Path

    from dotenv import load_dotenv

    from detour.voice.service import from_env

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    base = Path(os.environ.get("DETOUR_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")
    svc = from_env(dict(os.environ), base / "audio")
    if not svc.enabled:
        raise SystemExit("Voice is off: set ELEVENLABS_API_KEY (and not DETOUR_VOICE=off).")
    print(warm(svc))
