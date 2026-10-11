from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ValidationError

from detour.audit import AuditEntry, AuditLog
from detour.engine.disruptions import Disruption
from detour.engine.models import Plan, Scenario
from detour.events import EventBus
from detour.session import ApiError, Preview, Session, diff_json


class DisruptionBody(BaseModel):
    disruption: Disruption
    confirmed_by: str | None = None


class ConfirmBody(BaseModel):
    confirmed_by: str


class PlanBody(BaseModel):
    mode: Literal["auto", "demo", "solve"] = "auto"


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


def create_app(audit_path: Path | None = None, start_demo: bool = True) -> FastAPI:
    app = FastAPI(title="DeTour", version="0.4.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    bus = EventBus()
    audit = AuditLog(audit_path, on_append=lambda e: bus.publish({"type": "audit", "entry": e.model_dump()}))
    session = Session(audit, bus)
    app.state.session, app.state.bus, app.state.audit = session, bus, audit

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


def default_audit_path() -> Path:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    base = Path(os.environ.get("DETOUR_DATA_DIR") or Path(__file__).resolve().parents[1] / "data")
    return base / "audit.jsonl"
