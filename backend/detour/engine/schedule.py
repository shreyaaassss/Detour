"""Route timing: arrival, wait, service, departure and load at every stop (FR-4)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import Delivery, Route, Stop, Vehicle, hhmm
from .travel import TravelModel


@dataclass
class RouteEval:
    route: Route
    feasible: bool
    violation: str | None = None
    violated_delivery: str | None = None


def evaluate_route(
    vehicle: Vehicle,
    deliveries: Sequence[Delivery],
    travel: TravelModel,
    start_location: str,
    start_time: float,
) -> RouteEval:
    """Time a fixed delivery order. Stops after the first violation are not computed."""
    t = max(start_time, vehicle.available_from)
    loc = start_location
    load = sum(d.size for d in deliveries)
    initial_load = load
    stops: list[Stop] = []
    travel_total = 0.0
    violation: str | None = None
    bad: str | None = None

    if load > vehicle.capacity:
        violation = f"load {load} exceeds capacity {vehicle.capacity}"

    for d in deliveries:
        if violation:
            break
        leg = travel.travel(loc, d.location, t)
        arrival = t + leg
        if arrival > d.window_end:
            violation = f"{d.id}: arrives {hhmm(arrival)}, window closes {hhmm(d.window_end)}"
            bad = d.id
            break
        service_start = max(arrival, d.window_start)
        departure = service_start + d.service_time
        if departure > vehicle.shift_end:
            violation = f"{d.id}: finishes {hhmm(departure)}, after shift end {hhmm(vehicle.shift_end)}"
            bad = d.id
            break
        load -= d.size
        stops.append(
            Stop(
                delivery_id=d.id,
                location=d.location,
                arrival=arrival,
                wait=service_start - arrival,
                service_start=service_start,
                departure=departure,
                load_after=load,
            )
        )
        travel_total += leg
        t, loc = departure, d.location

    route = Route(
        vehicle_id=vehicle.id,
        start_location=start_location,
        start_time=max(start_time, vehicle.available_from),
        initial_load=initial_load,
        stops=stops,
        travel_minutes=travel_total,
    )
    return RouteEval(route, violation is None, violation, bad)
