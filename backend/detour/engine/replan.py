"""Replan from the state at time T (FR-10).

Completed stops stay fixed. A stop in progress, and the next stop of a vehicle that is
mid-leg, are committed too: the model has no road positions, so a vehicle cannot be
redirected before it arrives. A failed vehicle gets no stops after its failure time; its
parcels are collected from the breakdown site by whoever the plan chooses.
"""

from __future__ import annotations

from dataclasses import dataclass

from detour.validator import Report, validate

from .diff import Ref
from .disruptions import (
    DisruptionError,
    RoadClosure,
    UrgentDelivery,
    VehicleFailure,
    describe,
    effective_time,
    validate_disruption,
)
from .models import Closure, Delivery, Pickup, Plan, Scenario, Stop
from .schedule import item_id
from .solver import Problem, VState, solve_problem
from .travel import TravelModel

HANDOVER_MINUTES = 5.0


class PlanInvalid(Exception):
    """A revised plan failed the independent validator and must not be shown as valid."""

    def __init__(self, report: Report):
        super().__init__("; ".join(v.message for v in report.violations[:3]))
        self.report = report


@dataclass
class ReplanResult:
    scenario: Scenario
    plan: Plan
    report: Report
    frozen: dict[str, list[Stop]]
    now: float
    cause: str


def freeze_prefixes(plan: Plan, now: float, failing: set[str]) -> dict[str, list[Stop]]:
    """Per vehicle: the stops that can no longer change at time `now`."""
    out: dict[str, list[Stop]] = {}
    for r in plan.routes:
        prefix: list[Stop] = []
        prev_dep = r.start_time
        for s in r.stops:
            if s.arrival <= now or (s.frozen and r.vehicle_id not in failing):  # done, in progress, or committed
                prefix.append(s.model_copy(update={"frozen": True}))
            elif r.vehicle_id not in failing and prev_dep + s.idle <= now:  # mid-leg: committed
                prefix.append(s.model_copy(update={"frozen": True}))
                break
            else:
                break
            prev_dep = s.departure
        out[r.vehicle_id] = prefix
    return out


def _suffix(plan: Plan, vid: str, frozen: list[Stop]) -> list[Stop]:
    return plan.route(vid).stops[len(frozen) :]


def replan(
    scenario: Scenario,
    plan: Plan,
    disruption: RoadClosure | VehicleFailure | UrgentDelivery,
    *,
    now: float | None = None,
) -> ReplanResult:
    validate_disruption(scenario, disruption)
    now = effective_time(disruption) if now is None else now
    if plan.as_of is not None and now < plan.as_of - 1e-9:
        raise DisruptionError("a change cannot take effect before the current plan's time")
    cause = describe(scenario, disruption)

    failing = {disruption.vehicle_id} if isinstance(disruption, VehicleFailure) else set()
    frozen = freeze_prefixes(plan, now, failing)
    pending_pickups = {
        s.delivery_id for r in plan.routes for s in r.stops[len(frozen[r.vehicle_id]) :] if s.kind == "pickup"
    }

    # parcels that could not be placed earlier but are still loaded on a vehicle
    aboard_unplaced = {u.delivery_id: u.vehicle_id for u in plan.unplaced if u.vehicle_id}

    # --- revised scenario -------------------------------------------------------------------
    closures = list(scenario.closures)
    vehicles = list(scenario.vehicles)
    deliveries = {d.id: d for d in scenario.deliveries}
    new_pickups: set[str] = set()

    if isinstance(disruption, RoadClosure):
        closures.append(
            Closure(
                a=disruption.a,
                b=disruption.b,
                start=max(disruption.start, now + 1e-6),
                end=disruption.end,
                added_minutes=disruption.added_minutes,
                multiplier=disruption.multiplier,
            )
        )
    elif isinstance(disruption, VehicleFailure):
        broke = {"status": "failed", "failed_at": disruption.time, "failure_location": disruption.location}
        vehicles = [v.model_copy(update=broke) if v.id == disruption.vehicle_id else v for v in vehicles]
        aboard = [
            s.delivery_id
            for s in _suffix(plan, disruption.vehicle_id, frozen[disruption.vehicle_id])
            if s.kind == "delivery" and s.delivery_id not in pending_pickups
        ]
        aboard += [p for p, vid in aboard_unplaced.items() if vid == disruption.vehicle_id]
        for pid in aboard:  # parcels aboard the broken vehicle are now at the breakdown site
            deliveries[pid] = deliveries[pid].model_copy(
                update={"pickup": Pickup(location=disruption.location, ready_time=now, service_time=HANDOVER_MINUTES)}
            )
            new_pickups.add(pid)
    else:
        deliveries[disruption.id] = Delivery(
            id=disruption.id,
            location=disruption.location,
            size=disruption.size,
            window_start=disruption.window_start,
            window_end=disruption.window_end,
            service_time=disruption.service_time,
            priority=True,
            pickup=Pickup(
                location=disruption.pickup_location or scenario.depot, ready_time=now, service_time=HANDOVER_MINUTES
            ),
        )
        new_pickups.add(disruption.id)

    revised = scenario.model_copy(
        update={
            "closures": closures,
            "vehicles": vehicles,
            "deliveries": list(deliveries.values()),
        }
    )
    travel = TravelModel(revised.matrix, revised.closures)

    # --- problem for the solver -------------------------------------------------------------
    done = {s.delivery_id for fr in frozen.values() for s in fr if s.kind == "delivery"}
    jobs = {d.id: d for d in revised.deliveries if d.id not in done}
    states: dict[str, VState] = {}
    for v in revised.vehicles:
        r = plan.route(v.id) if any(x.vehicle_id == v.id for x in plan.routes) else None
        fr = frozen.get(v.id, [])
        rs_loc = r.start_location if r else v.start_location
        rs_time = r.start_time if r else max(revised.day_start, v.available_from)
        last_dep = fr[-1].departure if fr else rs_time
        loc = fr[-1].location if fr else rs_loc
        start = max(now, last_dep)
        states[v.id] = VState(
            v,
            fr,
            loc,
            start,
            start - last_dep,
            rs_loc,
            rs_time,
            live=v.status == "active",
            initial_load=r.initial_load if (r and fr) else None,
        )

    seq: dict[str, list[str]] = {}
    pinned: dict[str, str] = {}
    inherited: set[str] = set()
    for v in revised.vehicles:
        if v.status != "active":
            continue
        suffix = _suffix(plan, v.id, frozen[v.id])
        seq[v.id] = [item_id(s.kind, s.delivery_id) for s in suffix]
        inherited |= {s.delivery_id for s in suffix}
        if frozen[v.id]:  # the vehicle has left: parcels aboard stay on it (still at the depot, they are free)
            for s in suffix:
                if s.kind == "delivery" and s.delivery_id not in pending_pickups:
                    pinned[s.delivery_id] = v.id
            pinned.update({p: vid for p, vid in aboard_unplaced.items() if vid == v.id})
    todo = [d for d in jobs.values() if d.id not in inherited]

    # A parcel still needs its pickup unless it was collected at its current pickup site after
    # that pickup became due (a carrier that breaks down re-opens the parcel's pickup).
    needs_pickup = set()
    for pid, d in jobs.items():
        if d.pickup is None:
            continue
        spec = d.pickup
        collected = pid not in new_pickups and any(
            s.kind == "pickup"
            and s.delivery_id == pid
            and s.location == spec.location
            and s.service_start >= spec.ready_time - 1e-9
            for fr in frozen.values()
            for s in fr
        )
        if not collected:
            needs_pickup.add(pid)
    prob = Problem(
        revised,
        travel,
        states,
        jobs,
        pinned=pinned,
        ref=Ref.from_plan(plan),
        needs_pickup=needs_pickup,
    )
    new_plan = solve_problem(prob, seq=seq, todo=todo, as_of=now)

    failures = [{"vehicle_id": v.id, "time": v.failed_at} for v in revised.vehicles if v.failed_at is not None]
    report = validate(
        revised.model_dump(),
        new_plan.model_dump(),
        frozen={vid: [s.model_dump() for s in fr] for vid, fr in frozen.items()},
        failures=failures,
    )
    if not report.valid:
        raise PlanInvalid(report)
    return ReplanResult(revised, new_plan, report, frozen, now, cause)
