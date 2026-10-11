"""Who can rescue the main parcel, and what each choice does to everything else.

Each candidate is tried for real: the engine replans with that vehicle fixed as the rescuer, and the
independent validator checks the result. A candidate is feasible only if the rescued parcel is delivered
inside its window and the candidate's own remaining deliveries still meet theirs.
"""

from __future__ import annotations

from detour.engine.diff import build_diff
from detour.engine.disruptions import DisruptionError, VehicleFailure
from detour.engine.models import Plan, Scenario
from detour.engine.replan import PlanInvalid, ReplanResult, freeze_prefixes, replan
from detour.rescue.models import Candidate, Proposal


def remaining_parcels(plan: Plan, vehicle_id: str, now: float) -> list[str]:
    """Parcels still on a vehicle at `now`: stops it has not reached, plus parcels it could not place."""
    frozen = freeze_prefixes(plan, now, {vehicle_id}, {vehicle_id: now})[vehicle_id]
    route = plan.route(vehicle_id)
    left = [s.delivery_id for s in route.stops[len(frozen) :] if s.kind == "delivery"]
    left += [u.delivery_id for u in plan.unplaced if u.vehicle_id == vehicle_id]
    return left


def pick_primary(scenario: Scenario, parcels: list[str]) -> str | None:
    """The parcel the rescue is built around: priority first, then the earliest deadline."""
    ds = [d for d in scenario.deliveries if d.id in parcels]
    ds.sort(key=lambda d: (not d.priority, d.window_end, d.id))
    return ds[0].id if ds else None


def evaluate(
    scenario: Scenario, plan: Plan, failure: VehicleFailure, primary: str, vehicle_id: str, now: float
) -> tuple[Candidate, ReplanResult | None]:
    veh = scenario.vehicle(vehicle_id)
    cand = Candidate(vehicle_id=vehicle_id, driver=veh.driver, feasible=False)
    try:
        res = replan(scenario, plan, failure, now=now, assign={primary: vehicle_id})
    except (DisruptionError, PlanInvalid) as e:
        cand.reason = str(e)
        return cand, None

    placed = {s.delivery_id: s for r in res.plan.routes for s in r.stops if s.kind == "delivery"}
    route = res.plan.route(vehicle_id)
    drop = next((s for s in route.stops if s.kind == "delivery" and s.delivery_id == primary), None)
    if drop is None:
        why = next((u.reason for u in res.plan.unplaced if u.delivery_id == primary), "it cannot be delivered in time")
        cand.reason = why[0].upper() + why[1:]
        return cand, None

    # all pickups at the site share one handover: it starts at the first arrival and ends at the last departure
    handover = [s for s in route.stops if s.kind == "pickup" and s.location == failure.location]
    diff = build_diff(plan, res.plan, res.scenario, [res.cause], now)
    own_before = {s.delivery_id: s for s in plan.route(vehicle_id).stops if s.kind == "delivery" and not s.frozen}
    delays = [
        placed[i].service_start - s.service_start
        for i, s in own_before.items()
        if i in placed and placed[i].service_start > s.service_start
    ]
    cand.feasible = True
    cand.reach_site = min((s.arrival for s in handover), default=None)
    cand.leave_site = max((s.departure for s in handover), default=None)
    cand.delivery_time = drop.service_start
    cand.own_delay = max(delays, default=0.0)
    cand.impact = dict(diff.counts)
    cand.other_changes = [
        {"delivery_id": c.delivery_id, "status": c.status, "reason": c.reason}
        for c in diff.changes
        if c.status in ("moved", "broken", "new") and c.delivery_id != primary and not c.completed
    ]
    return cand, res


def rank(
    scenario: Scenario,
    plan: Plan,
    vehicle_id: str,
    location_id: str,
    now: float,
    version: int,
    exclude: set[str] | None = None,
) -> Proposal:
    """Rank every other vehicle as a possible rescuer for the vehicle that just broke down."""
    exclude = exclude or set()
    parcels = remaining_parcels(plan, vehicle_id, now)
    primary = pick_primary(scenario, parcels)
    prop = Proposal(
        vehicle_id=vehicle_id,
        location_id=location_id,
        failure_time=now,
        primary=primary,
        primary_place=None,
        primary_due=None,
        parcels=parcels,
        plan_version=version,
        candidates=[],
    )
    if primary is None:
        return prop
    d = scenario.delivery(primary)
    prop.primary_place = next(loc.name for loc in scenario.locations if loc.id == d.location)
    prop.primary_due = d.window_end

    failure = VehicleFailure(vehicle_id=vehicle_id, time=now, location=location_id)
    cands: list[Candidate] = []
    for v in scenario.vehicles:
        if v.id == vehicle_id or v.status != "active":
            continue
        if v.id in exclude:
            cands.append(
                Candidate(vehicle_id=v.id, driver=v.driver, feasible=False, reason="Already busy with another rescue")
            )
            continue
        c, _ = evaluate(scenario, plan, failure, primary, v.id, now)
        cands.append(c)
    ok = sorted((c for c in cands if c.feasible), key=lambda c: (c.delivery_time, c.own_delay, c.vehicle_id))
    for i, c in enumerate(ok, 1):
        c.rank = i
    bad = sorted((c for c in cands if not c.feasible), key=lambda c: c.vehicle_id)
    prop.candidates = [*ok, *bad]
    return prop
