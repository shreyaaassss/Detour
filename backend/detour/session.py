"""Application state: the scenario, the original and current plans, and every change made to them.

Nothing here talks HTTP. Every operation appends to the audit log, including refusals, and
publishes a state event so connected screens refresh.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from detour.audit import AuditLog
from detour.engine.diff import Diff, build_diff
from detour.engine.disruptions import (
    Disruption,
    DisruptionError,
    RoadClosure,
    UrgentDelivery,
    VehicleFailure,
    effective_time,
)
from detour.engine.models import Plan, Scenario, parse_hhmm
from detour.engine.replan import PlanInvalid, ReplanResult, replan
from detour.engine.scenario import DEMO_BASELINE, demo_presets, demo_scenario
from detour.engine.solver import plan_from_sequences, solve
from detour.events import EventBus
from detour.rescue.clock import SimClock
from detour.validator import Report, validate

AnyDisruption = RoadClosure | VehicleFailure | UrgentDelivery


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra: Any):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


@dataclass
class Preview:
    id: str
    disruption: AnyDisruption
    result: ReplanResult
    diff: Diff
    base_version: int
    actor: str


def diff_json(diff: Diff) -> dict[str, Any]:
    return {**diff.model_dump(), "counts": diff.counts}


def validate_plan(scenario: Scenario, plan: Plan) -> Report:
    """Validate a plan on its own: its flagged-frozen stops must be a clean prefix, and failed vehicles
    must have nothing after the failure time."""
    frozen = {r.vehicle_id: [s.model_dump() for s in r.stops if s.frozen] for r in plan.routes}
    failures = [{"vehicle_id": v.id, "time": v.failed_at} for v in scenario.vehicles if v.failed_at is not None]
    return validate(scenario.model_dump(), plan.model_dump(), frozen=frozen, failures=failures)


class Session:
    def __init__(self, audit: AuditLog, bus: EventBus, clock: SimClock | None = None):
        self.audit = audit
        self.bus = bus
        self.clock = clock or SimClock()
        self.listeners: list[Callable[[str], None]] = []
        self.version = 0
        self.kind = "demo"
        self.base_scenario: Scenario = demo_scenario()
        self.scenario: Scenario = self.base_scenario
        self.original: Plan | None = None
        self.plan: Plan | None = None
        self.report: Report | None = None
        self.applied: list[dict[str, Any]] = []
        self.causes: list[str] = []
        self.previews: dict[str, Preview] = {}
        self.approved_messages: dict[str, str] = {}  # delivery id -> the exact text the dispatcher approved

    # --- helpers ----------------------------------------------------------------------------
    @property
    def sim_time(self) -> float | None:
        return self.plan.as_of if self.plan else None

    def log(self, actor: str, action: str, details: dict[str, Any] | None = None) -> None:
        self.audit.append(actor, action, details, self.sim_time)

    def on_change(self, fn: Callable[[str], None]) -> None:
        self.listeners.append(fn)

    def _changed(self, reason: str) -> None:
        self.version += 1
        self.previews.clear()  # any pending preview was built on the old plan
        self.bus.publish({"type": "state", "version": self.version, "reason": reason})
        for fn in self.listeners:
            fn(reason)

    def incident_time(self) -> float:
        """The simulated time a new incident happens at: now, but never before the plan's own time."""
        return max(self.clock.now(), self.plan.as_of or 0.0)

    # --- scenario and baseline plan ---------------------------------------------------------
    def load_scenario(self, scenario: Scenario, kind: str, actor: str) -> None:
        self.base_scenario = self.scenario = scenario
        self.kind = kind
        self.original = self.plan = self.report = None
        self.applied, self.causes = [], []
        self.approved_messages = {}
        # the demo's breakdown story happens at 14:05; any other scenario starts at its day start
        self.clock.set(parse_hhmm("14:05") if kind == "demo" else scenario.day_start, speed=0)
        self.log(
            actor,
            "scenario_loaded",
            {
                "name": scenario.name,
                "kind": kind,
                "vehicles": len(scenario.vehicles),
                "deliveries": len(scenario.deliveries),
            },
        )
        self._changed("scenario_loaded")

    def build_plan(self, mode: str, actor: str) -> Plan:
        if mode == "auto":
            mode = "demo" if self.kind == "demo" else "solve"
        if mode == "demo":
            if self.kind != "demo":
                raise ApiError(
                    400, "not_demo", "the hand-assigned demo baseline only exists for the built-in demo scenario"
                )
            plan = plan_from_sequences(self.base_scenario, DEMO_BASELINE)
        elif mode == "solve":
            plan = solve(self.base_scenario)
        else:
            raise ApiError(400, "bad_mode", f"unknown mode {mode!r}; use auto, demo or solve")
        report = validate_plan(self.base_scenario, plan)
        if not report.valid:
            self.log(actor, "plan_rejected", {"mode": mode, "violations": [v.message for v in report.violations]})
            raise ApiError(
                409,
                "plan_invalid",
                "the plan failed validation and was not accepted",
                violations=[v.__dict__ for v in report.violations],
            )
        self.scenario, self.original, self.plan, self.report = self.base_scenario, plan, plan, report
        self.applied, self.causes = [], []
        self.log(
            actor,
            "plan_built",
            {
                "mode": mode,
                "total_travel_min": plan.total_travel,
                "valid": True,
                "unplaced": [{"delivery": u.delivery_id, "reason": u.reason} for u in plan.unplaced],
            },
        )
        self._changed("plan_built")
        return plan

    def reset_demo(self, actor: str) -> None:
        self.load_scenario(demo_scenario(), "demo", actor)
        self.build_plan("demo", actor)

    # --- disruptions ------------------------------------------------------------------------
    def compute(
        self,
        d: AnyDisruption,
        actor: str,
        assign: dict[str, str] | None = None,
        forbidden: dict[str, str] | None = None,
        now: float | None = None,
    ) -> Preview:
        if self.plan is None or self.original is None:
            raise ApiError(409, "no_plan", "build a plan before applying a disruption")
        try:
            result = replan(self.scenario, self.plan, d, now=now, assign=assign, forbidden=forbidden)
        except DisruptionError as e:
            self.log(actor, "disruption_refused", {"reason": str(e), "disruption": d.model_dump()})
            raise ApiError(422, "invalid_disruption", str(e)) from e
        except PlanInvalid as e:
            self.log(
                actor,
                "plan_rejected",
                {"violations": [v.message for v in e.report.violations], "disruption": d.model_dump()},
            )
            raise ApiError(
                409,
                "plan_invalid",
                "the revised plan failed validation and was not accepted",
                violations=[v.__dict__ for v in e.report.violations],
            ) from e
        diff = build_diff(self.original, result.plan, result.scenario, [*self.causes, result.cause], result.now)
        return Preview(uuid.uuid4().hex[:10], d, result, diff, self.version, actor)

    def preview(self, d: AnyDisruption, actor: str) -> Preview:
        p = self.compute(d, actor)
        self.previews[p.id] = p
        self.log(
            actor,
            "disruption_previewed",
            {
                "preview": p.id,
                "disruption": d.model_dump(),
                "cause": p.result.cause,
                "counts": p.diff.counts,
            },
        )
        return p

    def commit(self, p: Preview, actor: str, confirmed_by: str | None, meta: dict[str, Any] | None = None) -> None:
        r = p.result
        d = p.disruption
        self.scenario, self.plan, self.report = r.scenario, r.plan, r.report
        self.causes.append(r.cause)
        self.applied.append(
            {
                "n": len(self.applied) + 1,
                "type": d.type,
                "cause": r.cause,
                "at": r.now,
                "source": d.source,
                "confirmed_by": confirmed_by,
                "disruption": d.model_dump(),
            }
        )
        self.log(
            actor,
            "disruption_applied",
            {
                "disruption": d.model_dump(),
                "cause": r.cause,
                "confirmed_by": confirmed_by,
                "source": d.source,
                "counts": p.diff.counts,
                "validator": "passed",
                "unplaced": [{"delivery": u.delivery_id, "reason": u.reason} for u in r.plan.unplaced],
            },
        )
        self._changed("disruption_applied")

    def confirm(self, preview_id: str, actor: str, confirmed_by: str) -> Preview:
        p = self.previews.get(preview_id)
        if p is None:
            self.log(actor, "disruption_refused", {"reason": "unknown or expired preview", "preview": preview_id})
            raise ApiError(
                404, "unknown_preview", "no such preview; the plan may have changed, so preview the change again"
            )
        if p.base_version != self.version:
            self.log(actor, "disruption_refused", {"reason": "plan changed since preview", "preview": preview_id})
            raise ApiError(409, "stale_preview", "the plan changed since this preview; preview it again")
        self.commit(p, actor, confirmed_by)
        return p

    def apply(self, d: AnyDisruption, actor: str, confirmed_by: str | None) -> Preview:
        if d.source != "structured" and not confirmed_by:
            self.log(
                actor,
                "disruption_refused",
                {
                    "reason": "an interpreted report needs dispatcher confirmation",
                    "disruption": d.model_dump(),
                },
            )
            raise ApiError(
                422,
                "confirmation_required",
                "a disruption interpreted from text or voice must be confirmed by the dispatcher",
            )
        p = self.compute(d, actor)
        self.commit(p, actor, confirmed_by or actor)
        return p

    # --- validation and views ---------------------------------------------------------------
    def validate_current(self, actor: str, plan: Plan | None = None) -> Report:
        target = plan or self.plan
        if target is None:
            raise ApiError(409, "no_plan", "there is no plan to validate")
        report = validate_plan(self.scenario, target)
        self.log(
            actor,
            "validation_run",
            {
                "valid": report.valid,
                "violations": [v.message for v in report.violations],
                "supplied_plan": plan is not None,
            },
        )
        return report

    def diff(self) -> Diff | None:
        if self.plan is None or self.original is None:
            return None
        return build_diff(
            self.original, self.plan, self.scenario, self.causes, self.plan.as_of or self.scenario.day_start
        )

    def drafts(self) -> list[dict[str, Any]]:
        from detour.messages import drafts

        return drafts(self)

    def approve_message(self, delivery_id: str, actor: str) -> dict[str, Any]:
        found = next((m for m in self.drafts() if m["delivery_id"] == delivery_id), None)
        if found is None:
            raise ApiError(404, "no_draft", f"there is no customer message for {delivery_id}")
        self.approved_messages[delivery_id] = found["text"]
        self.log(actor, "customer_message_approved", {"delivery": delivery_id, "text": found["text"]})
        self.bus.publish({"type": "state", "version": self.version, "reason": "message_approved"})
        return {**found, "approved": True}

    def presets(self) -> dict[str, Any]:
        if self.kind != "demo":
            return {}
        return {name: d.model_dump() for name, d in demo_presets().items()}

    def state(self) -> dict[str, Any]:
        diff = self.diff()
        return {
            "version": self.version,
            "kind": self.kind,
            "as_of": self.sim_time,
            "scenario": self.scenario.model_dump(),
            "original": self.original.model_dump() if self.original else None,
            "plan": self.plan.model_dump() if self.plan else None,
            "report": self.report.as_dict() if self.report else None,
            "diff": diff_json(diff) if diff else None,
            "applied": self.applied,
        }


__all__ = ["ApiError", "Disruption", "Preview", "Session", "diff_json", "effective_time"]
