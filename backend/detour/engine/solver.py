"""Cheapest-insertion construction followed by local search (relocate, swap, 2-opt).

Deterministic: ties break by vehicle order then position, so a scenario always
produces the same plan.
"""
from __future__ import annotations

from .models import Delivery, Plan, Route, Scenario, Unplaced, Vehicle, hhmm
from .schedule import RouteEval, evaluate_route
from .travel import TravelModel

LIMITS = [
    "Heuristic: cheapest insertion plus local search. It finds good plans, not provably optimal ones.",
    "Objective is total driving time; return to depot is not counted.",
    "Time windows, capacity and shift end are hard constraints and are never relaxed.",
    "Travel times come from a simulated matrix, not live traffic or maps.",
    "Local search stops at a local optimum; a different insertion order may find a cheaper plan.",
]

EPS = 1e-9
MAX_PASSES = 200


class _State:
    """Routes as ordered lists of delivery ids, with cached evaluations."""

    def __init__(self, scenario: Scenario, travel: TravelModel):
        self.sc = scenario
        self.travel = travel
        self.vehicles = [v for v in scenario.vehicles if v.status == "active"]
        self.seq: dict[str, list[str]] = {v.id: [] for v in self.vehicles}
        self._cache: dict[tuple[str, tuple[str, ...]], RouteEval] = {}

    def eval(self, v: Vehicle, ids: list[str]) -> RouteEval:
        key = (v.id, tuple(ids))
        if key not in self._cache:
            ds = [self.sc.delivery(i) for i in ids]
            self._cache[key] = evaluate_route(v, ds, self.travel, v.start_location, self.sc.day_start)
        return self._cache[key]

    def cost(self, v: Vehicle, ids: list[str]) -> float:
        return self.eval(v, ids).route.travel_minutes

    def total(self) -> float:
        return sum(self.cost(v, self.seq[v.id]) for v in self.vehicles)


def _construct(st: _State, order: list[Delivery]) -> list[Delivery]:
    """Insert each delivery at its cheapest feasible position. Returns the ones left over."""
    leftover: list[Delivery] = []
    for d in order:
        best: tuple[float, int, int] | None = None
        for vi, v in enumerate(st.vehicles):
            cur = st.seq[v.id]
            base = st.cost(v, cur)
            for pos in range(len(cur) + 1):
                cand = cur[:pos] + [d.id] + cur[pos:]
                ev = st.eval(v, cand)
                if not ev.feasible:
                    continue
                key = (ev.route.travel_minutes - base, vi, pos)
                if best is None or key < best:
                    best = key
        if best is None:
            leftover.append(d)
        else:
            _, vi, pos = best
            v = st.vehicles[vi]
            st.seq[v.id].insert(pos, d.id)
    return leftover


def _try_apply(st: _State, changes: dict[str, list[str]]) -> bool:
    """Apply new sequences if all feasible and total cost strictly drops."""
    old = sum(st.cost(v, st.seq[v.id]) for v in st.vehicles if v.id in changes)
    new = 0.0
    for v in st.vehicles:
        if v.id in changes:
            ev = st.eval(v, changes[v.id])
            if not ev.feasible:
                return False
            new += ev.route.travel_minutes
    if new < old - EPS:
        st.seq.update({k: list(s) for k, s in changes.items()})
        return True
    return False


def _improve_once(st: _State) -> bool:
    vs = st.vehicles
    # relocate: move one delivery to another position, same or different route
    for a in vs:
        for i in range(len(st.seq[a.id])):
            for b in vs:
                src = st.seq[a.id][:i] + st.seq[a.id][i + 1:]
                dst_base = src if a.id == b.id else st.seq[b.id]
                for j in range(len(dst_base) + 1):
                    if a.id == b.id and j == i:
                        continue
                    moved = st.seq[a.id][i]
                    dst = dst_base[:j] + [moved] + dst_base[j:]
                    changes = {a.id: dst} if a.id == b.id else {a.id: src, b.id: dst}
                    if _try_apply(st, changes):
                        return True
    # swap: exchange two deliveries between two routes
    for ai, a in enumerate(vs):
        for b in vs[ai + 1:]:
            for i in range(len(st.seq[a.id])):
                for j in range(len(st.seq[b.id])):
                    sa, sb = list(st.seq[a.id]), list(st.seq[b.id])
                    sa[i], sb[j] = sb[j], sa[i]
                    if _try_apply(st, {a.id: sa, b.id: sb}):
                        return True
    # 2-opt: reverse a segment inside one route
    for a in vs:
        s = st.seq[a.id]
        for i in range(len(s) - 1):
            for j in range(i + 1, len(s)):
                cand = s[:i] + s[i:j + 1][::-1] + s[j + 1:]
                if _try_apply(st, {a.id: cand}):
                    return True
    return False


def explain_unplaced(st: _State, d: Delivery) -> str:
    """Specific reason a delivery could not be placed (FR-5)."""
    if not st.vehicles:
        return "no active vehicles"
    if d.size > max(v.capacity for v in st.vehicles):
        big = max(v.capacity for v in st.vehicles)
        return f"size {d.size} is larger than the biggest vehicle capacity ({big})"
    def first_arrival(v: Vehicle) -> float:
        leave = max(v.available_from, st.sc.day_start)
        return leave + st.travel.travel(v.start_location, d.location, leave)

    earliest = min(first_arrival(v) for v in st.vehicles)
    if earliest > d.window_end:
        return (
            f"window closes at {hhmm(d.window_end)} but the earliest any vehicle can arrive is {hhmm(earliest)}"
        )
    free = {v.id: v.capacity - sum(st.sc.delivery(i).size for i in st.seq[v.id]) for v in st.vehicles}
    if all(f < d.size for f in free.values()):
        return f"every vehicle is too full: size {d.size}, most free capacity is {max(free.values())}"
    return (
        "no vehicle can take it without another delivery missing its window or a vehicle "
        "running past its shift end"
    )


def solve(scenario: Scenario, travel: TravelModel | None = None) -> Plan:
    travel = travel or TravelModel(scenario.matrix, scenario.closures)
    st = _State(scenario, travel)
    # Most constrained first: earliest window close, then priority, then larger size.
    order = sorted(
        scenario.deliveries,
        key=lambda d: (d.window_end, not d.priority, -d.size, d.id),
    )
    leftover = _construct(st, order)

    for _ in range(MAX_PASSES):
        if not _improve_once(st):
            break
        # Local search may free room for deliveries that did not fit earlier.
        if leftover:
            leftover = _construct(st, leftover)

    routes: list[Route] = [st.eval(v, st.seq[v.id]).route for v in st.vehicles]
    unplaced = [Unplaced(delivery_id=d.id, reason=explain_unplaced(st, d)) for d in leftover]
    return Plan(
        scenario=scenario.name,
        routes=routes,
        unplaced=unplaced,
        total_travel=sum(r.travel_minutes for r in routes),
        solver="cheapest-insertion + local search (relocate, swap, 2-opt)",
        limits=LIMITS,
    )
