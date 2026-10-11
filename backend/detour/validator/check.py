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
        t = r["start_time"]
        loc = r["start_location"]
        if t < veh.get("available_from", 0) - TOL:
            bad("SHIFT_START", f"route starts {_fmt(t)} before the vehicle is available", vid)

        load = r["initial_load"]
        if load > cap:
            bad("CAPACITY", f"initial load {load} exceeds capacity {cap}", vid)
        expected_initial = sum(
            deliveries[s["delivery_id"]]["size"]
            for s in r["stops"]
            if s["delivery_id"] in deliveries and s.get("kind", "delivery") == "delivery"
        )
        pickups = sum(
            deliveries[s["delivery_id"]]["size"]
            for s in r["stops"]
            if s["delivery_id"] in deliveries and s.get("kind") == "pickup"
        )
        # Parcels delivered on this route but not picked up on it are on board from the start.
        if load != expected_initial - pickups and not frozen.get(vid):
            bad(
                "LOAD_MISMATCH",
                f"initial load {load} but deliveries on this route total {expected_initial - pickups}",
                vid,
            )

        for idx, s in enumerate(r["stops"]):
            did = s["delivery_id"]
            d = deliveries.get(did)
            if d is None:
                continue
            leg, base = _leg(matrix, closures, loc, s["location"], t)
            arrival = t + leg
            service_start = max(arrival, d["window_start"])
            departure = service_start + d["service_time"]
            kind = s.get("kind", "delivery")
            load += d["size"] if kind == "pickup" else -d["size"]

            if abs(s["arrival"] - arrival) > TOL:
                if abs(s["arrival"] - (t + base)) <= TOL and abs(leg - base) > TOL:
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
            if arrival > d["window_end"] + TOL:
                bad("WINDOW_LATE", f"{did}: arrives {_fmt(arrival)}, window closes {_fmt(d['window_end'])}", vid, did)
            if s["service_start"] < d["window_start"] - TOL:
                bad(
                    "WINDOW_EARLY",
                    f"{did}: service starts {_fmt(s['service_start'])} before window opens {_fmt(d['window_start'])}",
                    vid,
                    did,
                )
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
                ft = -1e9
            if ft is not None and not s.get("frozen") and not (s["arrival"] <= ft and s["departure"] <= ft):
                bad(
                    "FAILED_VEHICLE_STOP",
                    f"{vid} failed at {_fmt(ft) if ft > -1e8 else 'start'} but has stop {did} ({_fmt(s['arrival'])})",
                    vid,
                    did,
                )

            t, loc = s["departure"], s["location"]  # continue from the claimed state so one error is reported once

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
