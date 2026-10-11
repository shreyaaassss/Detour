"""Kept / moved / broken classification and plain-language reasons (FR-11, FR-12).

kept    same vehicle, window still met; any change in service time is shown
moved   different vehicle, or a materially different time or visit order
broken  cannot be served within its window, or cannot be served at all
new     an urgent delivery that was not in the original plan and was placed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from .models import Plan, Scenario, hhmm

MATERIAL_SHIFT = 15.0  # minutes of change in service time that counts as "moved"


@dataclass(frozen=True)
class Ref:
    """What a reference plan said about each delivery."""

    vehicle: dict[str, str]
    service: dict[str, float]
    order: dict[str, list[str]]  # vehicle -> delivery ids in visiting order

    @staticmethod
    def from_plan(plan: Plan) -> Ref:
        vehicle, service, order = {}, {}, {}
        for r in plan.routes:
            order[r.vehicle_id] = [s.delivery_id for s in r.stops if s.kind == "delivery"]
            for s in r.stops:
                if s.kind == "delivery":
                    vehicle[s.delivery_id] = r.vehicle_id
                    service[s.delivery_id] = s.service_start
        return Ref(vehicle, service, order)


def why_moved(ref: Ref, parcel: str, vehicle: str, service: float, order: list[str]) -> str | None:
    """None if the parcel counts as kept, otherwise 'vehicle', 'time' or 'order'."""
    if parcel not in ref.vehicle:
        return None  # not in the reference plan (e.g. an urgent delivery): cannot be "moved"
    if ref.vehicle[parcel] != vehicle:
        return "vehicle"
    if abs(service - ref.service[parcel]) >= MATERIAL_SHIFT:
        return "time"
    before = ref.order[vehicle]
    common = [d for d in order if d in before and d != parcel]
    if parcel in before:
        for q in common:
            if (order.index(q) < order.index(parcel)) != (before.index(q) < before.index(parcel)):
                return "order"
    return None


class Change(BaseModel):
    delivery_id: str
    status: Literal["kept", "moved", "broken", "new"]
    reason: str
    old_vehicle: str | None = None
    new_vehicle: str | None = None
    old_service: float | None = None
    new_service: float | None = None
    completed: bool = False


class Diff(BaseModel):
    as_of: float
    causes: list[str]
    changes: list[Change]

    @property
    def counts(self) -> dict[str, int]:
        out = {"kept": 0, "moved": 0, "broken": 0, "new": 0}
        for c in self.changes:
            out[c.status] += 1
        return out

    def change(self, delivery_id: str) -> Change:
        return next(c for c in self.changes if c.delivery_id == delivery_id)


def _who(scenario: Scenario, vid: str) -> str:
    v = scenario.vehicle(vid)
    return f"{vid} ({v.driver})" if v.driver else vid


def build_diff(original: Plan, revised: Plan, scenario: Scenario, causes: list[str], now: float) -> Diff:
    """Compare the day-start plan with the current one. `scenario` is the revised scenario."""
    ref = Ref.from_plan(original)
    cause = "; ".join(causes) if causes else "the plan was revised"
    loc_name = {loc.id: loc.name for loc in scenario.locations}
    placed: dict[str, tuple[str, float, float, bool, list[str]]] = {}  # id -> vehicle, service, arrival, frozen, order
    for r in revised.routes:
        order = [s.delivery_id for s in r.stops if s.kind == "delivery"]
        for s in r.stops:
            if s.kind == "delivery":
                placed[s.delivery_id] = (r.vehicle_id, s.service_start, s.arrival, s.frozen, order)
    unplaced = {u.delivery_id: u.reason for u in revised.unplaced}
    failed = {v.id: v for v in scenario.vehicles if v.status == "failed"}

    changes: list[Change] = []
    for d in scenario.deliveries:
        did = d.id
        win = f"{hhmm(d.window_start)}-{hhmm(d.window_end)}"
        old_v = ref.vehicle.get(did)
        old_s = ref.service.get(did)
        if did not in ref.vehicle:  # urgent delivery added after the original plan
            if did in placed:
                v, svc, _, _, _ = placed[did]
                changes.append(
                    Change(
                        delivery_id=did,
                        status="new",
                        new_vehicle=v,
                        new_service=svc,
                        reason=f"Urgent delivery added; {_who(scenario, v)} serves it at {hhmm(svc)} (window {win}).",
                    )
                )
            else:
                changes.append(
                    Change(
                        delivery_id=did,
                        status="broken",
                        reason=f"Urgent delivery cannot be placed: {unplaced.get(did, 'no feasible route')}.",
                    )
                )
            continue
        if did in unplaced or did not in placed:
            changes.append(
                Change(
                    delivery_id=did,
                    status="broken",
                    old_vehicle=old_v,
                    old_service=old_s,
                    reason=f"Cannot be delivered within its window ({win}): {unplaced.get(did, 'no feasible route')}. "
                    f"Cause: {cause}.",
                )
            )
            continue
        v, svc, _, frozen, order = placed[did]
        if frozen and svc + d.service_time <= now + 1e-9:
            changes.append(
                Change(
                    delivery_id=did,
                    status="kept",
                    old_vehicle=old_v,
                    new_vehicle=v,
                    old_service=old_s,
                    new_service=svc,
                    completed=True,
                    reason=f"Already delivered at {hhmm(svc)}, before the change.",
                )
            )
            continue
        how = why_moved(ref, did, v, svc, order)
        shift = svc - (old_s or svc)
        if how == "vehicle":
            old_failed = old_v in failed
            if old_failed:
                fv = failed[old_v]
                reason = (
                    f"Moved from {_who(scenario, old_v)} to {_who(scenario, v)}: {old_v} broke down at "
                    f"{loc_name.get(fv.failure_location or '', 'its location')} at {hhmm(fv.failed_at or now)}. "
                    f"{v} collects the parcel there and delivers at {hhmm(svc)} (window {win})."
                )
            else:
                reason = f"Moved from {old_v} to {v} because of {cause}; delivery at {hhmm(svc)} (window {win})."
            changes.append(
                Change(
                    delivery_id=did,
                    status="moved",
                    old_vehicle=old_v,
                    new_vehicle=v,
                    old_service=old_s,
                    new_service=svc,
                    reason=reason,
                )
            )
        elif how == "time":
            changes.append(
                Change(
                    delivery_id=did,
                    status="moved",
                    old_vehicle=old_v,
                    new_vehicle=v,
                    old_service=old_s,
                    new_service=svc,
                    reason=f"Same vehicle {v}, but delivery moves from {hhmm(old_s or 0)} to {hhmm(svc)} "
                    f"({shift:+.0f} min, window {win}) because of {cause}.",
                )
            )
        elif how == "order":
            changes.append(
                Change(
                    delivery_id=did,
                    status="moved",
                    old_vehicle=old_v,
                    new_vehicle=v,
                    old_service=old_s,
                    new_service=svc,
                    reason=f"Same vehicle {v}, but the visiting order changed; delivery at {hhmm(svc)} "
                    f"(was {hhmm(old_s or 0)}, window {win}) because of {cause}.",
                )
            )
        else:
            if abs(shift) < 1e-6:
                reason = "No change."
            else:
                reason = (
                    f"Same vehicle {v}; delivery shifts {shift:+.0f} min to {hhmm(svc)}, "
                    f"still inside its window ({win})."
                )
            changes.append(
                Change(
                    delivery_id=did,
                    status="kept",
                    old_vehicle=old_v,
                    new_vehicle=v,
                    old_service=old_s,
                    new_service=svc,
                    reason=reason,
                )
            )
    return Diff(as_of=now, causes=causes, changes=changes)
