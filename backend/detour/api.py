from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from detour.audit import AuditEntry, AuditLog
from detour.engine.disruptions import Disruption
from detour.engine.models import Plan, Scenario
from detour.events import EventBus
from detour.parsing.llm import Reader
from detour.rescue.clock import SimClock
from detour.rescue.routes import build_router
from detour.rescue.service import RescueConfig, RescueService
from detour.session import ApiError, Preview, Session, diff_json
from detour.telephony.config import CallSettings
from detour.telephony.routes import build_router as build_telephony_router
from detour.telephony.service import TelephonyService
from detour.voice.routes import build_router as build_voice_router
from detour.voice.service import VoiceService


class DisruptionBody(BaseModel):
    disruption: Disruption
    confirmed_by: str | None = None


class ConfirmBody(BaseModel):
    confirmed_by: str


class PlanBody(BaseModel):
    mode: Literal["auto", "demo", "solve"] = "auto"


class ParseBody(BaseModel):
    text: str
    source: Literal["text", "voice"] = "text"


class ValidateBody(BaseModel):
    plan: Plan | None = None


def _preview_json(p: Preview) -> dict[str, Any]:
    r = p.result
    return {
        "preview_id": p.id,
        "base_version": p.base_version,
        "as_of": r.now,
        "cause": r.cause,
        "plan": r.plan.model_dump(),
        "scenario": r.scenario.model_dump(),  # so a screen can draw the proposal, closures and breakdowns included
        "diff": diff_json(p.diff),
        "report": r.report.as_dict(),
    }


def create_app(
    audit_path: Path | None = None,
    start_demo: bool = True,
    start_ticker: bool = True,
    rescue_config: RescueConfig | None = None,
    llm: Reader | None = None,
    voice: VoiceService | None = None,
    telephony: TelephonyService | None = None,
    clock: SimClock | None = None,
    wall=None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        app.state.telephony.deliver = lambda fn: loop.call_soon_threadsafe(fn)  # phone events come from other threads
        task = None
        if start_ticker:  # the offer, call and approval timers run on this tick

            async def loop() -> None:
                while True:
                    rescue.tick()
                    await asyncio.sleep(0.25)

            task = asyncio.create_task(loop())
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="DeTour", version="0.6.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    bus = EventBus()
    audit = AuditLog(audit_path, on_append=lambda e: bus.publish({"type": "audit", "entry": e.model_dump()}))
    session = Session(audit, bus, clock or SimClock(wall=wall or time.time), llm)
    rescue = RescueService(session, rescue_config, **({"wall": wall} if wall else {}))
    app.state.session, app.state.bus, app.state.audit, app.state.rescue = session, bus, audit, rescue
    voice = voice or VoiceService(None)
    voice._log = lambda action, details: session.log("system", action, details)
    app.state.voice = voice
    tel = telephony or TelephonyService(CallSettings())
    app.state.telephony = tel
    rescue.attach_calls(tel)
    app.include_router(build_telephony_router(session, rescue, tel))
    app.include_router(build_router(session, rescue))
    app.include_router(build_voice_router(session, rescue, voice))

    if audit.archived:
        audit.append(
            "system", "audit_log_archived", {"reason": "previous log failed verification", "file": audit.archived.name}
        )
    audit.append("system", "server_started", {})
    if start_demo:
        session.reset_demo("system")

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError) -> JSONResponse:
        return JSONResponse({"code": e.code, "message": e.message, **e.extra}, status_code=e.status)

    @app.exception_handler(ValidationError)
    async def _validation_error(_: Request, e: ValidationError) -> JSONResponse:
        return JSONResponse(
            {
                "code": "invalid_input",
                "message": str(e.errors()[0]["msg"]),
                "errors": e.errors(include_url=False, include_context=False),
            },
            status_code=422,
        )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "version": session.version, "audit_entries": len(audit.entries)}

    # --- the website's contact form --------------------------------------------------------------
    inbox: list[dict[str, Any]] = []
    inbox_path = Path(audit_path).parent / "contact.jsonl" if audit_path else None

    @app.post("/site/contact")
    async def contact(body: ContactBody) -> dict[str, Any]:
        """Keep a visitor's message on the server. Nothing is emailed: no outside service is involved."""
        if len(inbox) >= MAX_CONTACT_MESSAGES:
            raise ApiError(429, "inbox_full", "The inbox is full for now. Please try again later.")
        note = {"id": len(inbox) + 1, "at": time.time(), **body.model_dump()}
        inbox.append(note)
        if inbox_path is not None:
            with contextlib.suppress(OSError):
                inbox_path.parent.mkdir(parents=True, exist_ok=True)
                with inbox_path.open("a") as f:
                    f.write(json.dumps(note, ensure_ascii=False) + "\n")
        session.log("visitor", "contact_message_received", {"id": note["id"], "topic": body.topic})
        return {"ok": True, "id": note["id"]}

    @app.get("/site/inbox")
    async def read_inbox(x_detour_admin: str | None = Header(None)) -> dict[str, Any]:
        """The team reads the messages here. Closed unless DETOUR_ADMIN_KEY is set, and then only with that key."""
        key = os.environ.get("DETOUR_ADMIN_KEY", "").strip()
        if not key or not x_detour_admin or not hmac.compare_digest(key, x_detour_admin):
            raise ApiError(404, "not_found", "Not found.")
        return {"messages": inbox}

    # --- scenario and plan ------------------------------------------------------------------
    @app.get("/state")
    async def state() -> dict[str, Any]:
        return session.state()

    @app.get("/scenario")
    async def get_scenario() -> dict[str, Any]:
        return {
            "kind": session.kind,
            "scenario": session.scenario.model_dump(),
            "original_scenario": session.base_scenario.model_dump(),
        }

    @app.post("/scenario")
    async def load_scenario(scenario: Scenario, x_actor: str = Header("dispatcher")) -> dict[str, Any]:
        session.load_scenario(scenario, "custom", x_actor)
        return {"version": session.version, "name": scenario.name}

    @app.post("/reset")
    async def reset(x_actor: str = Header("dispatcher")) -> dict[str, Any]:
        session.reset_demo(x_actor)
        return session.state()

    @app.post("/plan")
    async def build_plan(body: PlanBody | None = None, x_actor: str = Header("dispatcher")) -> dict[str, Any]:
        session.build_plan((body or PlanBody()).mode, x_actor)
        return session.state()

    @app.get("/plan")
    async def get_plan() -> dict[str, Any]:
        s = session.state()
        return {k: s[k] for k in ("version", "as_of", "plan", "original", "report")}

    @app.get("/plan/diff")
    async def get_diff() -> dict[str, Any]:
        d = session.diff()
        if d is None:
            raise ApiError(409, "no_plan", "there is no plan yet")
        return {"version": session.version, **diff_json(d)}

    # --- disruptions ------------------------------------------------------------------------
    @app.get("/presets")
    async def presets() -> dict[str, Any]:
        return session.presets()

    @app.post("/disruptions/preview")
    async def preview(body: DisruptionBody, x_actor: str = Header("dispatcher")) -> dict[str, Any]:
        return _preview_json(session.preview(body.disruption, x_actor))

    @app.post("/disruptions/parse")
    async def parse(body: ParseBody, x_actor: str = Header("dispatcher")) -> dict[str, Any]:
        res, p = session.interpret(body.text, body.source, x_actor)
        return {"parse": res.as_dict(), "preview": _preview_json(p)}

    @app.get("/interpreter")
    async def interpreter() -> dict[str, Any]:
        return {"mode": "llm" if session.llm else "rules", "model": getattr(session.llm, "model", None)}

    @app.post("/disruptions/{preview_id}/confirm")
    async def confirm(preview_id: str, body: ConfirmBody, x_actor: str = Header("dispatcher")) -> dict[str, Any]:
        session.confirm(preview_id, x_actor, body.confirmed_by)
        return session.state()

    @app.post("/disruptions")
    async def apply(body: DisruptionBody, x_actor: str = Header("dispatcher")) -> dict[str, Any]:
        session.apply(body.disruption, x_actor, body.confirmed_by)
        return session.state()

    # --- validator --------------------------------------------------------------------------
    @app.post("/validate")
    async def validate_plan(body: ValidateBody | None = None, x_actor: str = Header("dispatcher")) -> dict[str, Any]:
        return session.validate_current(x_actor, body.plan if body else None).as_dict()

    # --- audit ------------------------------------------------------------------------------
    @app.get("/audit")
    async def get_audit(limit: int = Query(200, ge=1, le=2000), after: int = Query(0, ge=0)) -> dict[str, Any]:
        entries: list[AuditEntry] = audit.tail(limit, after)
        return {"entries": [e.model_dump() for e in entries], "total": len(audit.entries), "chain": audit.verify()}

    @app.get("/audit/verify")
    async def verify_audit() -> dict[str, Any]:
        return audit.verify()

    # --- live updates -----------------------------------------------------------------------
    @app.get("/events")
    async def events(max_events: int | None = Query(None, ge=1)) -> StreamingResponse:
        hello = {"type": "hello", "version": session.version}
        return StreamingResponse(
            bus.stream(hello, max_events),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


MAX_CONTACT_MESSAGES = 200


class ContactBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    topic: Literal["question", "feedback", "pilot", "other"] = "question"
    message: str = Field(min_length=5, max_length=2000)


def default_audit_path() -> Path:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    base = Path(os.environ.get("DETOUR_DATA_DIR") or Path(__file__).resolve().parents[1] / "data")
    return base / "audit.jsonl"
