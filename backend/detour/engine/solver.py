"""Cheapest-insertion construction followed by local search (relocate, swap, 2-opt).

The same search plans a fresh day and replans from a mid-day state. A replan hands it:
  - frozen prefixes (completed or committed stops that never change),
  - the parcels still to place and which vehicle each is pinned to (already aboard),
  - a reference plan so "moved" deliveries can be counted.

Objective, compared in this order: fewest unplaced, fewest moved, least driving time.
Deterministic: ties break by vehicle order then position.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .diff import Ref, why_moved
from .models import Delivery, Plan, Route, Scenario, Stop, Unplaced, Vehicle, hhmm
from .schedule import Item, RouteEval, assemble_route, evaluate_items, item_id, split_item_id
from .travel import TravelModel

LIMITS = [
    "Heuristic: cheapest insertion plus local search. It finds good plans, not provably optimal ones.",
    "Objective, in order: fewest undeliverable, fewest moved, least driving time. Return to depot is not counted.",
    "Time windows, capacity and shift end are hard constraints and are never relaxed.",
    "Travel times come from a simulated matrix, not live traffic or maps.",
    "Local search stops at a local optimum; a different insertion order may find a cheaper plan.",
    "A parcel already loaded on a running vehicle stays on it: it is delivered by that vehicle or reported broken.",
    "A vehicle in mid-leg must finish that leg; it cannot be redirected before its next stop.",
]

EPS = 1e-9
MAX_PASSES = 300
INF = float("inf")


@dataclass
class VState:
    vehicle: Vehicle
    prefix: list[Stop]
    start_location: str  # where the free part of the route begins
    start_time: float  # when the vehicle leaves it
    idle: float
    route_start_location: str
    route_start_time: float
    live: bool = True
    initial_load: int | None = None  # load the vehicle left with; None = work it out from the route


@dataclass
class Problem:
    scenario: Scenario
    travel: TravelModel
    states: dict[str, VState]
    jobs: dict[str, Delivery]  # parcels the search may place
    pinned: dict[str, str] = field(default_factory=dict)  # parcel -> vehicle it is aboard
    ref: Ref | None = None
    needs_pickup: set[str] = field(default_factory=set)  # parcels whose pickup has not happened yet
    assigned: dict[str, str] = field(default_factory=dict)  # parcel -> the vehicle a person chose for it (a rescue)


def fresh_problem(scenario: Scenario, travel: TravelModel | None = None) -> Problem:
    travel = travel or TravelModel(scenario.matrix, scenario.closures)
    states = {}
    for v in scenario.vehicles:
        t0 = max(scenario.day_start, v.available_from)
        states[v.id] = VState(v, [], v.start_location, t0, 0.0, v.start_location, t0, live=v.status == "active")
    jobs = {d.id: d for d in scenario.deliveries}
    return Problem(scenario, travel, states, jobs, needs_pickup={d.id for d in jobs.values() if d.pickup})


class Search:
    def __init__(self, prob: Problem, seq: dict[str, list[str]] | None = None):
        self.p = prob
        self.live = [s for s in prob.states.values() if s.live]
        self.seq: dict[str, list[str]] = {s.vehicle.id: [] for s in self.live}
        if seq:
            for k, v in seq.items():
                if k in self.seq:
                    self.seq[k] = list(v)
        self._cache: dict[tuple[str, tuple[str, ...]], RouteEval] = {}
        self._obj: dict[tuple[str, tuple[str, ...]], tuple[int, float]] = {}

    # --- evaluation ---------------------------------------------------------------------
    def items(self, ids: list[str]) -> list[Item]:
        out = []
        for i in ids:
            kind, pid = split_item_id(i)
            out.append((kind, self.p.jobs[pid]))
        return out

    def eval(self, vid: str, ids: list[str]) -> RouteEval:
        key = (vid, tuple(ids))
        if key not in self._cache:
            st = self.p.states[vid]
            prev = (st.prefix[-1].kind, st.prefix[-1].location) if st.prefix else None
            load = st.prefix[-1].load_after if st.prefix else None
            self._cache[key] = evaluate_items(
                st.vehicle, self.items(ids), self.p.travel, st.start_location, st.start_time, st.idle, prev, load
            )
        return self._cache[key]

    def obj(self, vid: str, ids: list[str]) -> tuple[int, float]:
        """(moved, driving minutes) of one route; (inf, inf) if infeasible."""
        key = (vid, tuple(ids))
        if key in self._obj:
            return self._obj[key]
        ev = self.eval(vid, ids)
        if not ev.feasible:
            res: tuple[int, float] = (10**9, INF)
        else:
            moved = 0
            if self.p.ref is not None:
                st = self.p.states[vid]
                order = [s.delivery_id for s in st.prefix if s.kind == "delivery"]
                order += [s.delivery_id for s in ev.stops if s.kind == "delivery"]
                for s in ev.stops:
                    if s.kind == "delivery" and why_moved(self.p.ref, s.delivery_id, vid, s.service_start, order):
                        moved += 1
            res = (moved, ev.travel_minutes)
        self._obj[key] = res
        return res

    def total_obj(self) -> tuple[int, float]:
        parts = [self.obj(v, s) for v, s in self.seq.items()]
        return sum(p[0] for p in parts), sum(p[1] for p in parts)

    def placed(self) -> set[str]:
        return {split_item_id(i)[1] for s in self.seq.values() for i in s}

    # --- moves --------------------------------------------------------------------------
    def allowed(self, pid: str) -> list[VState]:
        pin = self.p.pinned.get(pid) or self.p.assigned.get(pid)
        return [s for s in self.live if pin is None or s.vehicle.id == pin]

    def variants(self, ids: list[str], pid: str) -> list[list[str]]:
        """All ways to insert parcel `pid` (with its pickup first, if it needs one)."""
        n = len(ids)
        if pid in self.p.needs_pickup and item_id("pickup", pid) not in ids:
            pk = item_id("pickup", pid)
            return [ids[:i] + [pk] + ids[i:j] + [pid] + ids[j:] for i in range(n + 1) for j in range(i, n + 1)]
        return [ids[:i] + [pid] + ids[i:] for i in range(n + 1)]

    def insert_job(self, pid: str) -> bool:
        best: tuple[int, float, int, int] | None = None
        best_choice: tuple[str, list[str]] | None = None
        for vi, st in enumerate(self.live):
            if st not in self.allowed(pid):
                continue
            vid = st.vehicle.id
            cur = self.seq[vid]
            base = self.obj(vid, cur)
            for pos, cand in enumerate(self.variants(cur, pid)):
                o = self.obj(vid, cand)
                if o[1] == INF:
                    continue
                key = (o[0] - base[0], round(o[1] - base[1], 6), vi, pos)
                if best is None or key < best:
                    best, best_choice = key, (vid, cand)
        if best_choice is None:
            return False
        self.seq[best_choice[0]] = best_choice[1]
        return True

    def _apply_if_better(self, changes: dict[str, list[str]]) -> bool:
        old_m = old_t = new_m = new_t = 0.0
        for vid, ids in changes.items():
            o = self.obj(vid, self.seq[vid])
            n = self.obj(vid, ids)
            if n[1] == INF:
                return False
            old_m, old_t, new_m, new_t = old_m + o[0], old_t + o[1], new_m + n[0], new_t + n[1]
        if new_m < old_m or (new_m == old_m and new_t < old_t - EPS):
            self.seq.update({k: list(v) for k, v in changes.items()})
            return True
        return False

    def _jobs_in(self, vid: str) -> list[str]:
        out: list[str] = []
        for i in self.seq[vid]:
            pid = split_item_id(i)[1]
            if pid not in out:
                out.append(pid)
        return out

    @staticmethod
    def _without(ids: list[str], pid: str) -> list[str]:
        return [i for i in ids if split_item_id(i)[1] != pid]

    def improve_once(self) -> bool:
        live = self.live
        # relocate a whole job (a parcel and its pickup, if it has one) to the best place
        for a in live:
            for pid in self._jobs_in(a.vehicle.id):
                src = self._without(self.seq[a.vehicle.id], pid)
                for b in self.allowed(pid):
                    base = src if b.vehicle.id == a.vehicle.id else self.seq[b.vehicle.id]
                    for dst in self.variants(base, pid):
                        if b.vehicle.id == a.vehicle.id:
                            if dst == self.seq[a.vehicle.id]:
                                continue
                            changes = {a.vehicle.id: dst}
                        else:
                            changes = {a.vehicle.id: src, b.vehicle.id: dst}
                        if self._apply_if_better(changes):
                            return True
        # swap two free, plain parcels between routes
        for ai, a in enumerate(live):
            for b in live[ai + 1 :]:
                for i, ia in enumerate(self.seq[a.vehicle.id]):
                    if not self._swappable(ia, b):
                        continue
                    for j, ib in enumerate(self.seq[b.vehicle.id]):
                        if not self._swappable(ib, a):
                            continue
                        sa, sb = list(self.seq[a.vehicle.id]), list(self.seq[b.vehicle.id])
                        sa[i], sb[j] = sb[j], sa[i]
                        if self._apply_if_better({a.vehicle.id: sa, b.vehicle.id: sb}):
                            return True
        # 2-opt: reverse a segment inside one route (precedence breakers are rejected)
        for a in live:
            s = self.seq[a.vehicle.id]
            for i in range(len(s) - 1):
                for j in range(i + 1, len(s)):
                    cand = s[:i] + s[i : j + 1][::-1] + s[j + 1 :]
                    if self._apply_if_better({a.vehicle.id: cand}):
                        return True
        return False

    def _swappable(self, iid: str, other: VState) -> bool:
        kind, pid = split_item_id(iid)
        if kind != "delivery" or pid in self.p.needs_pickup:
            return False
        pin = self.p.pinned.get(pid)
        return pin is None or pin == other.vehicle.id

    # --- repair of an inherited route ---------------------------------------------------
    def repair(self, vid: str) -> list[str]:
        """Remove parcels until the inherited route is feasible. Returns the removed parcels."""
        removed: list[str] = []
        while True:
            ids = self.seq[vid]
            ev = self.eval(vid, ids)
            if ev.feasible:
                return removed
            cut = ev.violated_index if ev.violated_index is not None else len(ids) - 1
            best: tuple[tuple, str] | None = None
            for pid in dict.fromkeys(split_item_id(i)[1] for i in ids[: cut + 1]):
                trial = self._without(ids, pid)
                te = self.eval(vid, trial)
                reach = len(trial) if te.feasible else (te.violated_index or 0)
                key = (not te.feasible, -reach, self.p.jobs[pid].priority, self.p.jobs[pid].size, pid)
                if best is None or key < best[0]:
                    best = (key, pid)
            assert best is not None
            self.seq[vid] = self._without(ids, best[1])
            removed.append(best[1])


def order_key(d: Delivery) -> tuple:
    return (d.window_end, not d.priority, -d.size, d.id)


def explain_unplaced(se: Search, d: Delivery) -> str:
    """Specific reason a delivery could not be placed (FR-5, FR-12)."""
    if not se.live:
        return "no vehicle is available"
    big = max(s.vehicle.capacity for s in se.live)
    if d.size > big:
        return f"size {d.size} is larger than the biggest vehicle capacity ({big})"

    def first_arrival(st: VState) -> float:
        t, loc = st.start_time, st.start_location
        if d.pickup is not None:
            t = max(t + se.p.travel.travel(loc, d.pickup.location, t), d.pickup.ready_time) + d.pickup.service_time
            loc = d.pickup.location
        return t + se.p.travel.travel(loc, d.location, t)

    cands = se.allowed(d.id)
    pin = se.p.pinned.get(d.id)
    who = se.p.assigned.get(d.id)
    chosen = None
    if who:
        v = se.p.scenario.vehicle(who)
        chosen = f"{v.driver} ({who})" if v.driver else who
    if not cands:
        return f"{chosen or pin} is not available"
    earliest = min(first_arrival(s) for s in cands)
    if earliest > d.window_end:
        if chosen:
            return (
                f"{chosen} could only deliver it at {hhmm(earliest)}, after its window closes at {hhmm(d.window_end)}"
            )
        if pin:
            return (
                f"it is aboard {pin}, which cannot reach it before {hhmm(earliest)}, "
                f"but its window closes at {hhmm(d.window_end)}"
            )
        return f"window closes at {hhmm(d.window_end)} but the earliest any vehicle can arrive is {hhmm(earliest)}"
    free = {s.vehicle.id: s.vehicle.capacity - se.eval(s.vehicle.id, se.seq[s.vehicle.id]).peak_load for s in cands}
    if all(f < d.size for f in free.values()):
        return f"every vehicle is too full: size {d.size}, most free capacity is {max(free.values())}"
    if chosen:
        return f"{chosen} cannot take it without making its own deliveries miss their windows"
    if pin:
        return f"it is aboard {pin} and cannot be delivered without another delivery missing its window"
    return "no vehicle can take it without another delivery missing its window or a vehicle running past its shift end"


def solve_problem(
    prob: Problem,
    seq: dict[str, list[str]] | None = None,
    todo: list[Delivery] | None = None,
    as_of: float | None = None,
    optimise: bool = True,
    forbidden: dict[str, str] | None = None,
) -> Plan:
    """`forbidden` maps parcels that must not be placed to the reason they are not delivered."""
    forbidden = forbidden or {}
    if forbidden and seq:
        seq = {v: [i for i in ids if split_item_id(i)[1] not in forbidden] for v, ids in seq.items()}
    se = Search(prob, seq)
    pending: list[Delivery] = [d for d in (todo if todo is not None else prob.jobs.values()) if d.id not in forbidden]
    for st in se.live:
        pending += [prob.jobs[p] for p in se.repair(st.vehicle.id)]
    leftover: list[Delivery] = []
    for d in sorted(pending, key=order_key):
        if not se.insert_job(d.id):
            leftover.append(d)

    for _ in range(MAX_PASSES if optimise else 0):
        if not se.improve_once():
            break
        if leftover:  # local search may have freed room
            leftover = [d for d in leftover if not se.insert_job(d.id)]

    sizes = {d.id: d.size for d in prob.scenario.deliveries}
    routes: list[Route] = []
    for st in prob.states.values():
        suffix = se.eval(st.vehicle.id, se.seq[st.vehicle.id]).stops if st.live else []
        routes.append(
            assemble_route(
                st.vehicle.id, st.route_start_location, st.route_start_time, st.prefix, suffix, sizes, st.initial_load
            )
        )
    unplaced = [
        Unplaced(delivery_id=d.id, reason=explain_unplaced(se, d), vehicle_id=prob.pinned.get(d.id)) for d in leftover
    ]
    unplaced += [Unplaced(delivery_id=pid, reason=why) for pid, why in forbidden.items() if pid in prob.jobs]
    return Plan(
        scenario=prob.scenario.name,
        routes=routes,
        unplaced=unplaced,
        total_travel=sum(r.travel_minutes for r in routes),
        solver="cheapest-insertion + local search (relocate, swap, 2-opt)",
        limits=LIMITS,
        as_of=as_of,
    )


def solve(scenario: Scenario, travel: TravelModel | None = None) -> Plan:
    """Plan a fresh day (FR-2)."""
    prob = fresh_problem(scenario, travel)
    return solve_problem(prob, todo=sorted(scenario.deliveries, key=order_key))


def plan_from_sequences(scenario: Scenario, sequences: dict[str, list[str]], travel: TravelModel | None = None) -> Plan:
    """Time a hand-chosen assignment (for example the demo baseline). Raises if it is infeasible."""
    prob = fresh_problem(scenario, travel)
    se = Search(prob, sequences)
    for vid, ids in sequences.items():
        ev = se.eval(vid, ids)
        if not ev.feasible:
            raise ValueError(f"{vid}: {ev.violation}")
    return solve_problem(prob, seq=sequences, todo=[], optimise=False)
