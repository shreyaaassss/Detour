from __future__ import annotations

from detour.engine.disruptions import RoadClosure, UrgentDelivery, VehicleFailure
from detour.engine.models import Scenario, hhmm


def summarise(d: RoadClosure | VehicleFailure | UrgentDelivery, sc: Scenario, now: float) -> str:
    """What was understood, in words built from the fields themselves (never from the model's own wording),
    so the dispatcher checks the real values before anything is applied."""
    name = {loc.id: loc.name for loc in sc.locations}
    if isinstance(d, RoadClosure):
        effect = f"{d.added_minutes:g} minutes slower" if d.added_minutes else f"{d.multiplier:g} times as slow"
        return (
            f"The road between {name[d.a]} and {name[d.b]} is {effect} from {hhmm(d.start)} to {hhmm(d.end)}. "
            f"Reported at {hhmm(d.reported_at if d.reported_at is not None else now)}."
        )
    if isinstance(d, VehicleFailure):
        v = next((x for x in sc.vehicles if x.id == d.vehicle_id), None)
        who = f"{v.id} ({v.driver})" if v and v.driver else d.vehicle_id
        return f"{who} broke down at {name[d.location]} at {hhmm(d.time)}."
    pickup = name[d.pickup_location] if d.pickup_location else "the depot"
    return (
        f"A new urgent delivery {d.id}: size {d.size} to {name[d.location]}, collected from {pickup}, "
        f"to be delivered between {hhmm(d.window_start)} and {hhmm(d.window_end)}. Added at {hhmm(d.time)}."
    )
