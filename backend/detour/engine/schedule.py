"""Route timing: arrival, wait, service, departure and load at every stop (FR-4).

A route is a frozen prefix (already done or committed) plus a suffix of items that the
solver is free to choose. This module times a suffix from a given start state.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .models import Delivery, Route, Stop, Vehicle, hhmm
from .travel import TravelModel

Item = tuple[str, Delivery]  # ("delivery" | "pickup", parcel)

HOLD_THRESHOLD = 20.0  # a vehicle waits at a customer up to this long; beyond it, it holds back instead


def item_id(kind: str, parcel_id: str) -> str:
    return parcel_id if kind == "delivery" else f"@{parcel_id}"


def split_item_id(iid: str) -> tuple[str, str]:
    return ("pickup", iid[1:]) if iid.startswith("@") else ("delivery", iid)


@dataclass
class RouteEval:
    stops: list[Stop]
    feasible: bool
    violation: str | None = None
    violated_index: int | None = None
    travel_minutes: float = 0.0
    end_location: str = ""
    end_time: float = 0.0
    start_load: int = 0
    peak_load: int = 0
    violated_delivery: str | None = None
    extra: dict = field(default_factory=dict)


def evaluate_items(
    vehicle: Vehicle,
    items: Sequence[Item],
    travel: TravelModel,
    start_location: str,
    start_time: float,
    idle: float = 0.0,
    previous: tuple[str, str] | None = None,
    start_load: int | None = None,
) -> RouteEval:
    """Time `items` in order. `start_time` is when the vehicle leaves `start_location`
    (already including `idle`, which is only recorded on the first stop). `previous` is the
    (kind, location) of the stop just before `items`, so a pickup can share its handover.
    `start_load` is the load already aboard when a frozen prefix exists, including parcels the
    plan can no longer deliver.

    Stops after the first violation are not computed.
    """
    pickups_here = {p.id for kind, p in items if kind == "pickup"}
    if start_load is None:  # a fresh route: everything delivered here without a pickup is loaded at the start
        start_load = sum(p.size for kind, p in items if kind == "delivery" and p.id not in pickups_here)
    load = peak = start_load
    t, loc = start_time, start_location
    stops: list[Stop] = []
    travel_total = 0.0
    picked: set[str] = set()
    violation: str | None = None
    vidx: int | None = None
    vdel: str | None = None

    if load > vehicle.capacity:
        violation = f"load {load} exceeds capacity {vehicle.capacity}"

    pending_idle = idle
    prev_kind, prev_loc = previous if previous else (None, None)
    for idx, (kind, p) in enumerate(items):
        if violation:
            break
        place = p.pickup.location if kind == "pickup" and p.pickup else p.location
        if kind == "delivery" and p.id in pickups_here and p.id not in picked:
            violation, vidx, vdel = f"{p.id}: delivered before it is picked up", idx, p.id
            break
        leg = travel.travel(loc, place, t)
        arrival = t + leg
        hold = 0.0
        if kind == "delivery" and arrival < p.window_start - HOLD_THRESHOLD:
            # Too early by more than the threshold: hold the vehicle where it is instead of
            # parking at the customer. Shown as idle time, and the vehicle stays available.
            later = t + (p.window_start - arrival)
            leg2 = travel.travel(loc, place, later)
            if later + leg2 <= p.window_end:
                hold, leg = later - t, leg2
                arrival = later + leg
        if kind == "pickup":
            assert p.pickup is not None
            service_start = max(arrival, p.pickup.ready_time)
            shared = prev_kind == "pickup" and prev_loc == place
            service = 0.0 if shared else p.pickup.service_time
            load += p.size
            picked.add(p.id)
        else:
            if arrival > p.window_end:
                violation = f"{p.id}: arrives {hhmm(arrival)}, window closes {hhmm(p.window_end)}"
                vidx, vdel = idx, p.id
                break
            service_start = max(arrival, p.window_start)
            service = p.service_time
            load -= p.size
        departure = service_start + service
        peak = max(peak, load)
        if load > vehicle.capacity:
            violation = f"after {p.id} load {load} exceeds capacity {vehicle.capacity}"
            vidx, vdel = idx, p.id
            break
        if departure > vehicle.shift_end:
            violation = f"{p.id}: finishes {hhmm(departure)}, after shift end {hhmm(vehicle.shift_end)}"
            vidx, vdel = idx, p.id
            break
        stops.append(
            Stop(
                delivery_id=p.id,
                location=place,
                kind=kind,  # type: ignore[arg-type]
                idle=pending_idle + hold,
                arrival=arrival,
                wait=service_start - arrival,
                service_start=service_start,
                departure=departure,
                load_after=load,
            )
        )
        travel_total += leg
        pending_idle = 0.0
        t, loc = departure, place
        prev_kind, prev_loc = kind, place

    return RouteEval(
        stops=stops,
        feasible=violation is None,
        violation=violation,
        violated_index=vidx,
        travel_minutes=travel_total,
        end_location=loc,
        end_time=t,
        start_load=start_load,
        peak_load=peak,
        violated_delivery=vdel,
    )


def route_travel_minutes(stops: Sequence[Stop], start_time: float) -> float:
    total, prev = 0.0, start_time
    for s in stops:
        total += s.arrival - s.idle - prev
        prev = s.departure
    return total


def assemble_route(
    vehicle_id: str,
    start_location: str,
    start_time: float,
    prefix: Sequence[Stop],
    suffix: Sequence[Stop],
    sizes: dict[str, int],
    initial_load: int | None = None,
) -> Route:
    """Join the frozen prefix and the timed suffix into one route.

    initial_load is what the vehicle carried when it left the depot. It is history: it is passed
    in for a replan, otherwise it is every parcel delivered here that was not picked up en route."""
    stops = [*prefix, *suffix]
    picked = {s.delivery_id for s in stops if s.kind == "pickup"}
    initial = initial_load
    if initial is None:
        initial = sum(sizes[s.delivery_id] for s in stops if s.kind == "delivery" and s.delivery_id not in picked)
    return Route(
        vehicle_id=vehicle_id,
        start_location=start_location,
        start_time=start_time,
        initial_load=initial,
        stops=stops,
        travel_minutes=route_travel_minutes(stops, start_time),
    )
