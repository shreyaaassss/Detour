from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from detour.engine.models import parse_hhmm
from detour.rescue.service import RescueService
from detour.session import ApiError, Session


class ReportBody(BaseModel):
    driver: str
    transcript: str = ""
    language: str | None = None
    location_id: str | None = None  # the driver picked the place from the list
    breakdown: bool | None = None  # the driver pressed "Vehicle broke down"
    source: Literal["text", "voice", "buttons"] = "text"
    engine: Literal["elevenlabs", "browser", "typed"] | None = None  # what turned speech into this text


class ConfirmBody(BaseModel):
    confirmed: bool = True
    location_id: str | None = None


class ApproveBody(BaseModel):
    approved_by: str
    shortlist: list[str]
    proposal_version: int
    role: Literal["head", "backup"] = "head"


class RejectBody(BaseModel):
    by: str


class RespondBody(BaseModel):
    response: Literal["accept", "decline"]
    via: Literal["tap", "call"] = "tap"
    by: str | None = None


class CallBody(BaseModel):
    offer_id: str
    outcome: Literal["answered", "confirmed", "declined", "no_answer", "voicemail", "busy", "ambiguous", "unclear"]


class ClockBody(BaseModel):
    sim_time: str | None = None  # HH:MM
    speed: float | None = None  # simulated minutes per real minute; 0 pauses


def build_router(s: Session, svc: RescueService) -> APIRouter:
    r = APIRouter()

    @r.post("/incidents/report")
    async def report(body: ReportBody) -> dict[str, Any]:
        inc = svc.report(
            body.driver, body.transcript, body.language, body.location_id, body.breakdown, body.source, body.engine
        )
        return {"server_time": svc.wall(), "incident": svc.incident_view(inc)}

    @r.get("/incidents")
    async def incidents() -> dict[str, Any]:
        return svc.overview()

    @r.get("/incidents/{incident_id}")
    async def incident(incident_id: str) -> dict[str, Any]:
        return {"server_time": svc.wall(), "incident": svc.incident_view(svc._get(incident_id))}

    @r.post("/incidents/{incident_id}/confirm")
    async def confirm(incident_id: str, body: ConfirmBody) -> dict[str, Any]:
        inc = svc.confirm(incident_id, body.confirmed, body.location_id)
        return {"server_time": svc.wall(), "incident": svc.incident_view(inc)}

    @r.get("/incidents/{incident_id}/proposal")
    async def proposal(incident_id: str) -> dict[str, Any]:
        inc = svc._get(incident_id)
        if inc.proposal is None:
            raise ApiError(409, "no_proposal", "There is no proposal yet for this report.")
        return {"server_time": svc.wall(), "proposal": inc.proposal.model_dump(), "state": inc.state}

    @r.post("/incidents/{incident_id}/approve")
    async def approve(incident_id: str, body: ApproveBody) -> dict[str, Any]:
        inc = svc.approve(incident_id, body.approved_by, body.shortlist, body.proposal_version, body.role)
        return {"server_time": svc.wall(), "incident": svc.incident_view(inc)}

    @r.post("/incidents/{incident_id}/reject")
    async def reject(incident_id: str, body: RejectBody) -> dict[str, Any]:
        return {"server_time": svc.wall(), "incident": svc.incident_view(svc.reject(incident_id, body.by))}

    @r.get("/offers")
    async def offers(driver: str) -> dict[str, Any]:
        return {"server_time": svc.wall(), "offers": svc.open_offers(driver)}

    @r.post("/offers/{offer_id}/respond")
    async def respond(offer_id: str, body: RespondBody) -> dict[str, Any]:
        inc = svc.respond(offer_id, body.response, body.via, body.by)
        return {"server_time": svc.wall(), "incident": svc.incident_view(inc)}

    @r.post("/telephony/webhook")
    async def webhook(body: CallBody) -> dict[str, Any]:
        inc = svc.telephony_event(body.offer_id, body.outcome)
        return {"server_time": svc.wall(), "incident": svc.incident_view(inc)}

    @r.get("/clock")
    async def get_clock() -> dict[str, Any]:
        return {"sim": s.clock.now(), "speed": s.clock.speed, "server_time": svc.wall()}

    @r.post("/clock")
    async def set_clock(body: ClockBody) -> dict[str, Any]:
        t = None
        if body.sim_time is not None:
            m = re.fullmatch(r"(\d{1,2}):(\d{2})", body.sim_time.strip())
            if not m or int(m[1]) > 23 or int(m[2]) > 59:
                raise ApiError(422, "bad_time", "Enter the time as HH:MM, for example 14:05.")
            t = parse_hhmm(body.sim_time)
        s.clock.set(t, body.speed)
        s.log("dispatcher", "clock_set", {"sim_time": body.sim_time, "speed": body.speed})
        return {"sim": s.clock.now(), "speed": s.clock.speed, "server_time": svc.wall()}

    @r.get("/notifications")
    async def notifications(to: str, after: int = Query(0, ge=0)) -> dict[str, Any]:
        return {"server_time": svc.wall(), "notifications": svc.notifications(to, after)}

    @r.get("/messages")
    async def messages() -> dict[str, Any]:
        return {"messages": s.drafts()}

    @r.post("/messages/{delivery_id}/approve")
    async def approve_message(delivery_id: str, x_actor: str = Header("dispatcher")) -> dict[str, Any]:
        return s.approve_message(delivery_id, x_actor)

    return r
