from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

TOL = 0.01  # minutes


@dataclass
class Violation:
    code: str
    message: str
    vehicle_id: str | None = None
    delivery_id: str | None = None


@dataclass
class Report:
    valid: bool
    violations: list[Violation] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def codes(self) -> set[str]:
        return {v.code for v in self.violations}


CHECKS = [
    "every delivery is routed or reported unplaced exactly once",
    "routes use known vehicles and known deliveries",
    "arrival, wait and departure times match a from-scratch recomputation",
    "every parcel with a pickup is collected before it is delivered, on the same vehicle",
    "closures are applied to legs that depart inside the closure period",
    "arrival is no later than the window close; service never starts before the window opens",
    "load never exceeds capacity at any point and never goes negative",
    "vehicles finish within their shift",
    "frozen (completed) stops are unchanged and form the start of the route",
    "a failed vehicle has no stops after its failure time",
]


def _fmt(t: float) -> str:
    m = round(t)
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


def _leg(matrix: dict, closures: list[dict], a: str, b: str, depart: float) -> tuple[float, float]:
    """Return (leg time with closures, leg time ignoring closures)."""
    if a == b:
        return 0.0, 0.0
    base = float(matrix[a][b])
    t = base
    for c in closures:
        if {c["a"], c["b"]} == {a, b} and c["start"] <= depart < c["end"]:
            t = t * c.get("multiplier", 1.0) + c.get("added_minutes", 0.0)
    return t, base


def validate(
    scenario: dict,
    plan: dict,
    *,
    frozen: dict[str, list[dict]] | None = None,
    failures: list[dict] | None = None,
    extra_closures: list[dict] | None = None,
) -> Report:
    """Check `plan` against `scenario`.

    frozen: vehicle_id -> stops (dicts with delivery_id, arrival, departure) that are already
        completed and must open that vehicle's route unchanged.
    failures: [{"vehicle_id", "time"}]. A stop is allowed only if it arrives at or before the
        failure time and is finished by it; a stop in progress at the failure time is allowed
        only if it is frozen.
    extra_closures: closures in force that are not in the scenario (e.g. just applied).
    """
    frozen = frozen or {}
    failures = failures or []
    out: list[Violation] = []

    def bad(code: str, msg: str, v: str | None = None, d: str | None = None) -> None:
        out.append(Violation(code, msg, v, d))

    vehicles = {v["id"]: v for v in scenario["vehicles"]}
    deliveries = {d["id"]: d for d in scenario["deliveries"]}
    matrix = scenario["matrix"]
    closures = [*scenario.get("closures", []), *(extra_closures or [])]
    fail_time = {f["vehicle_id"]: f["time"] for f in failures}

    # --- coverage ---------------------------------------------------------------------------
    seen: dict[str, int] = {}
    for r in plan["routes"]:
        if r["vehicle_id"] not in vehicles:
            bad("UNKNOWN_VEHICLE", f"route for unknown vehicle {r['vehicle_id']}", r["vehicle_id"])
        for s in r["stops"]:
            if s.get("kind", "delivery") == "delivery":
                seen[s["delivery_id"]] = seen.get(s["delivery_id"], 0) + 1
    for u in plan.get("unplaced", []):
        seen[u["delivery_id"]] = seen.get(u["delivery_id"], 0) + 1
    for did, n in seen.items():
        if did not in deliveries:
            bad("UNKNOWN_DELIVERY", f"{did} is not a known delivery", d=did)
        elif n > 1:
            bad("DUPLICATE_DELIVERY", f"{did} appears {n} times in the plan", d=did)
    for did in deliveries:
        if did not in seen:
            bad("MISSING_DELIVERY", f"{did} is neither routed nor reported unplaced", d=did)

    # --- per-route re-timing ----------------------------------------------------------------
    for r in plan["routes"]:
        vid = r["vehicle_id"]
        veh = vehicles.get(vid)
        if veh is None:
            continue
        cap = veh["capacity"]
        stops = r["stops"]
        t = r["start_time"]
        loc = r["start_location"]
        if t < veh.get("available_from", 0) - TOL:
            bad("SHIFT_START", f"route starts {_fmt(t)} before the vehicle is available", vid)

        # pickups and deliveries on this route
        d_idx = {s["delivery_id"]: i for i, s in enumerate(stops) if s.get("kind", "delivery") == "delivery"}
        p_idx = {s["delivery_id"]: i for i, s in enumerate(stops) if s.get("kind") == "pickup"}
        for did, pi in p_idx.items():
            if did not in deliveries:
                continue
            if did not in d_idx:
                if not stops[pi].get("frozen"):
                    bad("PICKUP_ORPHAN", f"{did} is picked up but never delivered by {vid}", vid, did)
            elif pi > d_idx[did]:
                bad("PICKUP_ORDER", f"{did} is delivered before it is picked up", vid, did)
        for did in d_idx:
            if did in deliveries and deliveries[did].get("pickup") and did not in p_idx:
                bad(
                    "MISSING_PICKUP",
                    f"{did} must be collected from {deliveries[did]['pickup']['location']} first",
                    vid,
                    did,
                )

        load = r["initial_load"]
        if load > cap:
            bad("CAPACITY", f"initial load {load} exceeds capacity {cap}", vid)

        prev_kind, prev_loc = None, None
        for s in stops:
            did = s["delivery_id"]
            d = deliveries.get(did)
            if d is None:
                continue
            kind = s.get("kind", "delivery")
            idle = s.get("idle", 0.0)
            if idle < -TOL:
                bad("TIME_MISMATCH", f"{did}: negative idle time", vid, did)
            leave = t + idle
            leg, base = _leg(matrix, closures, loc, s["location"], leave)
            arrival = leave + leg
            frozen_stop = bool(s.get("frozen"))

            if kind == "pickup":
                spec = d.get("pickup")
                if frozen_stop or spec is None or spec["location"] != s["location"]:
                    # A completed pickup is history: its parcel may since have been given a new pickup
                    # (its carrier broke down), so it is not re-timed against the current spec.
                    if not frozen_stop:
                        bad("PICKUP_LOCATION", f"{did}: pickup stop is not at the pickup location", vid, did)
                    service_start, departure = s["service_start"], s["departure"]
                else:
                    service_start = max(arrival, spec["ready_time"])
                    shared = prev_kind == "pickup" and prev_loc == s["location"]
                    departure = service_start + (0.0 if shared else spec["service_time"])
                load += d["size"]
            else:
                if s["location"] != d["location"]:
                    bad("PICKUP_LOCATION", f"{did}: stop is not at the delivery location", vid, did)
                service_start = max(arrival, d["window_start"])
                departure = service_start + d["service_time"]
                load -= d["size"]
                if arrival > d["window_end"] + TOL:
                    bad(
                        "WINDOW_LATE",
                        f"{did}: arrives {_fmt(arrival)}, window closes {_fmt(d['window_end'])}",
                        vid,
                        did,
                    )
                if s["service_start"] < d["window_start"] - TOL:
                    bad(
                        "WINDOW_EARLY",
                        f"{did}: service starts {_fmt(s['service_start'])} before it opens {_fmt(d['window_start'])}",
                        vid,
                        did,
                    )

            if abs(s["arrival"] - arrival) > TOL:
                if abs(s["arrival"] - (leave + base)) <= TOL and abs(leg - base) > TOL:
                    bad(
                        "CLOSURE_IGNORED",
                        f"{did}: claims arrival {_fmt(s['arrival'])} but a closure makes it {_fmt(arrival)}",
                        vid,
                        did,
                    )
                else:
                    bad(
                        "TIME_MISMATCH",
                        f"{did}: claims arrival {_fmt(s['arrival'])}, recomputed {_fmt(arrival)}",
                        vid,
                        did,
                    )
            if abs(s["wait"] - (service_start - arrival)) > TOL or abs(s["departure"] - departure) > TOL:
                bad("TIME_MISMATCH", f"{did}: wait/departure do not match recomputation", vid, did)
            if load > cap:
                bad("CAPACITY", f"after {did} load {load} exceeds capacity {cap}", vid, did)
            if load < 0:
                bad("CAPACITY", f"after {did} load is negative ({load})", vid, did)
            if s["load_after"] != load:
                bad("LOAD_MISMATCH", f"{did}: claims load {s['load_after']}, recomputed {load}", vid, did)
            if departure > veh.get("shift_end", 1e9) + TOL:
                bad(
                    "SHIFT_END", f"{did}: finishes {_fmt(departure)} after shift end {_fmt(veh['shift_end'])}", vid, did
                )

            # failed vehicle rule
            ft = fail_time.get(vid)
            if ft is None and veh.get("status") == "failed":
                ft = veh.get("failed_at") if veh.get("failed_at") is not None else -1e9
            if ft is not None and not frozen_stop and not (s["arrival"] <= ft and s["departure"] <= ft):
                when = _fmt(ft) if ft > -1e8 else "the start"
                bad(
                    "FAILED_VEHICLE_STOP", f"{vid} failed at {when} but has stop {did} ({_fmt(s['arrival'])})", vid, did
                )

            t, loc = s["departure"], s["location"]  # continue from the claimed state so an error is reported once
            prev_kind, prev_loc = kind, s["location"]

    # --- frozen stops -----------------------------------------------------------------------
    for vid, fz in frozen.items():
        route = next((r for r in plan["routes"] if r["vehicle_id"] == vid), None)
        stops = route["stops"] if route else []
        if len(stops) < len(fz):
            bad("FROZEN_CHANGED", f"{vid}: {len(fz)} completed stops but route has only {len(stops)}", vid)
            continue
        for want, got in zip(fz, stops, strict=False):
            same = (
                want["delivery_id"] == got["delivery_id"]
                and abs(want["arrival"] - got["arrival"]) <= TOL
                and abs(want["departure"] - got["departure"]) <= TOL
            )
            if not same:
                bad(
                    "FROZEN_CHANGED",
                    f"{vid}: completed stop {want['delivery_id']} was altered or reordered",
                    vid,
                    want["delivery_id"],
                )
    for r in plan["routes"]:
        flags = [bool(s.get("frozen")) for s in r["stops"]]
        n_frozen = sum(flags)
        if n_frozen and flags != [True] * n_frozen + [False] * (len(flags) - n_frozen):
            bad("FROZEN_NOT_PREFIX", "frozen stops must come first in the route", r["vehicle_id"])
        if n_frozen != len(frozen.get(r["vehicle_id"], [])) and frozen:
            bad(
                "FROZEN_CHANGED",
                f"{r['vehicle_id']}: expected {len(frozen.get(r['vehicle_id'], []))} frozen stops, found {n_frozen}",
                r["vehicle_id"],
            )

    return Report(valid=not out, violations=out, checks=list(CHECKS))
