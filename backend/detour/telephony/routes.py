from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

from fastapi import APIRouter, Header
from pydantic import BaseModel

from detour.rescue.service import RescueService
from detour.rescue.strings import say
from detour.session import ApiError, Session
from detour.telephony.service import TelephonyService
from detour.voice.client import VoiceError


class AgentReport(BaseModel):
    offer_id: str = ""
    decision: Literal["confirmed", "declined", "unclear"]
    method: Literal["voice", "keypad"] | None = None


class BrowserStarted(BaseModel):
    driver: str | None = None
    conversation_id: str


class BrowserOpen(BaseModel):
    driver: str | None = None


class TestBody(BaseModel):
    driver: str | None = None


def build_router(s: Session, svc: RescueService, tel: TelephonyService) -> APIRouter:
    r = APIRouter()

    @r.get("/telephony/status")
    async def status() -> dict[str, Any]:
        return tel.status()

    @r.post("/telephony/agent")
    async def agent_report(body: AgentReport, x_detour_key: str | None = Header(None)) -> dict[str, Any]:
        """The phone agent's decision tool calls this. Only the agent, holding the shared secret, may."""
        if not tel.check_secret(x_detour_key):
            s.log("telephony", "agent_report_refused", {"reason": "wrong or missing key"})
            raise ApiError(401, "bad_key", "Not allowed.")
        if body.offer_id.startswith("test"):  # a test call from the dispatcher screen, not a rescue
            tel.history.append(
                {
                    "offer": body.offer_id,
                    "what": "test answered",
                    "detail": f"{body.decision} ({body.method})",
                    "at": time.time(),
                }
            )
            s.log("telephony", "test_call_answered", {"decision": body.decision, "method": body.method})
            return {"ok": True}
        try:
            svc.telephony_event(body.offer_id, body.decision, body.method)
        except ApiError as e:  # too late or unknown: say so quietly so the agent does not get confused mid-call
            return {"ok": False, "reason": e.code}
        return {"ok": True}

    @r.post("/offers/{offer_id}/browser-session")
    async def browser_session(offer_id: str, body: BrowserOpen | None = None) -> dict[str, Any]:
        """Plan B for the phone line: the driver's page talks to the same call agent through the browser."""
        driver = body.driver if body else None
        ctx = svc.browser_call_context(offer_id, driver)
        try:
            url = await asyncio.to_thread(tel.browser_session)
        except VoiceError as e:
            s.log("telephony", "browser_call_unavailable", {"offer": offer_id, "reason": e.message})
            raise ApiError(409, "browser_call_unavailable", e.message) from e
        return {"signed_url": url, **ctx}

    @r.post("/offers/{offer_id}/browser-session/started")
    async def browser_started(offer_id: str, body: BrowserStarted) -> dict[str, Any]:
        svc.browser_call_started(offer_id, body.driver, body.conversation_id)
        return {"ok": True}

    @r.post("/telephony/test")
    async def test_call(body: TestBody | None = None) -> dict[str, Any]:
        """Ring a listed number with a harmless test, to check the phone line before the demo."""
        who = (body.driver if body else None) or None
        ok, why = tel.can_call(who)
        if not ok:
            raise ApiError(409, "calls_not_ready", f"A test call cannot be placed: {why}.")
        lang = tel.language_for("hi")
        script = {
            "hi": "यह डीटूर की टेस्ट कॉल है, ऑटोमेटेड। अगर आप मुझे सुन पा रहे हैं तो 1 दबाएँ या कन्फर्म बोलें।",
            "mr": "हा डीटूरचा चाचणी कॉल आहे, स्वयंचलित. मी तुम्हाला ऐकू येत असल्यास 1 दाबा किंवा कन्फर्म म्हणा.",
            "en": "This is an automated test call from DeTour. If you can hear me, press 1 or say confirm.",
        }[lang if lang in ("hi", "mr", "en") else "en"]
        offer_id = f"test-{int(time.time())}"
        started = await asyncio.to_thread(
            tel.start,
            offer_id,
            who,
            script=script,
            language=lang,
            variables={"parcel": "test", "site": "test", "dest": "test", "due": "test", "driver": who or ""},
            ring_seconds=25,
            on_event=lambda o, outcome, how: tel.history.append(
                {"offer": o, "what": "test " + outcome, "detail": how or "", "at": time.time()}
            ),
            is_open=lambda: True,
        )
        s.log("dispatcher", "test_call_requested", {"driver": who, "started": started})
        return {"started": started, "language": lang, "say": say("stood_down", "en")}

    return r
