"""The three disruptions (FR-6, FR-7, FR-8), checked against the scenario before use.

A disruption naming something the scenario does not contain is rejected with a
DisruptionError, never guessed at (FR-9). Interpreted text or voice input produces
one of these models; the dispatcher confirms it before it is applied.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .models import Scenario, hhmm


class DisruptionError(ValueError):
    pass


class _Base(BaseModel):
    source: Literal["structured", "text", "voice"] = "structured"
    confirmed_by: str | None = None


class RoadClosure(_Base):
    type: Literal["road_closure"] = "road_closure"
    a: str
    b: str
    start: float
    end: float
    added_minutes: float = 0
    multiplier: float = 1.0
    reported_at: float | None = None  # defaults to the closure start


class VehicleFailure(_Base):
    type: Literal["vehicle_failure"] = "vehicle_failure"
    vehicle_id: str
    time: float
    location: str


class UrgentDelivery(_Base):
    type: Literal["urgent_delivery"] = "urgent_delivery"
    id: str
    location: str
    size: int
    window_start: float
    window_end: float
    service_time: float = 5
    pickup_location: str | None = None  # where the parcel is collected; defaults to the depot
    time: float  # when it was added


Disruption = Annotated[RoadClosure | VehicleFailure | UrgentDelivery, Field(discriminator="type")]


def effective_time(d: RoadClosure | VehicleFailure | UrgentDelivery) -> float:
    if isinstance(d, RoadClosure):
        return d.reported_at if d.reported_at is not None else d.start
    return d.time


def validate_disruption(scenario: Scenario, d: RoadClosure | VehicleFailure | UrgentDelivery) -> None:
    locs = {loc.id for loc in scenario.locations}

    def known(loc: str, what: str) -> None:
        if loc not in locs:
            raise DisruptionError(f"unknown location {loc!r} ({what}); known: {', '.join(sorted(locs))}")

    if isinstance(d, RoadClosure):
        known(d.a, "closure end A")
        known(d.b, "closure end B")
        if d.a == d.b:
            raise DisruptionError("a closure needs two different locations")
        if d.end <= d.start:
            raise DisruptionError("the closure must end after it starts")
        if d.added_minutes <= 0 and d.multiplier <= 1.0:
            raise DisruptionError("the closure must add travel time (added_minutes > 0 or multiplier > 1)")
        if d.added_minutes < 0 or d.multiplier < 1.0:
            raise DisruptionError("a closure cannot make travel faster")
    elif isinstance(d, VehicleFailure):
        known(d.location, "failure location")
        veh = next((v for v in scenario.vehicles if v.id == d.vehicle_id), None)
        if veh is None:
            raise DisruptionError(f"unknown vehicle {d.vehicle_id!r}")
        if veh.status == "failed":
            raise DisruptionError(f"vehicle {d.vehicle_id} has already failed")
    else:
        known(d.location, "delivery location")
        if d.pickup_location:
            known(d.pickup_location, "pickup location")
        if any(x.id == d.id for x in scenario.deliveries):
            raise DisruptionError(f"delivery id {d.id!r} already exists")
        if d.size <= 0:
            raise DisruptionError("size must be positive")
        if d.window_end < d.window_start:
            raise DisruptionError("the window ends before it opens")


def describe(scenario: Scenario, d: RoadClosure | VehicleFailure | UrgentDelivery) -> str:
    """Plain-language cause, used in reasons shown to the dispatcher and in customer notes."""
    name = {loc.id: loc.name for loc in scenario.locations}
    if isinstance(d, RoadClosure):
        extra = f"+{d.added_minutes:g} min" if d.added_minutes else f"x{d.multiplier:g} travel time"
        return f"the {name[d.a]}-{name[d.b]} road closure ({hhmm(d.start)}-{hhmm(d.end)}, {extra})"
    if isinstance(d, VehicleFailure):
        v = next(v for v in scenario.vehicles if v.id == d.vehicle_id)
        who = f"{v.id} ({v.driver})" if v.driver else v.id
        return f"{who} broke down at {name[d.location]} at {hhmm(d.time)}"
    return f"urgent delivery {d.id} added at {hhmm(d.time)}"
