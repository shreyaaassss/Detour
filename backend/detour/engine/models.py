"""Data model. Times are minutes since midnight."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Location(_Frozen):
    id: str
    name: str
    x: float
    y: float


class Vehicle(_Frozen):
    id: str
    capacity: int
    start_location: str
    driver: str | None = None
    available_from: float = 0
    shift_end: float = 24 * 60
    status: Literal["active", "failed"] = "active"
    failed_at: float | None = None
    failure_location: str | None = None


class Pickup(_Frozen):
    """A parcel that must be collected somewhere before it can be delivered: the breakdown
    site for a rescued parcel, or the depot for an urgent one. Consecutive pickups at the same
    place share one handover."""

    location: str
    ready_time: float
    service_time: float = 5


class Delivery(_Frozen):
    id: str
    location: str
    size: int
    window_start: float
    window_end: float
    service_time: float = 5
    priority: bool = False
    pickup: Pickup | None = None


class Closure(_Frozen):
    """Extra travel time between two locations (both directions) for [start, end)."""

    a: str
    b: str
    start: float
    end: float
    added_minutes: float = 0
    multiplier: float = 1.0


class Scenario(BaseModel):
    name: str
    depot: str
    day_start: float
    locations: list[Location]
    vehicles: list[Vehicle]
    deliveries: list[Delivery]
    matrix: dict[str, dict[str, float]]
    closures: list[Closure] = []

    @model_validator(mode="after")
    def _check_references(self) -> Scenario:
        ids = {loc.id for loc in self.locations}
        if self.depot not in ids:
            raise ValueError(f"depot {self.depot!r} is not a known location")
        for v in self.vehicles:
            if v.start_location not in ids:
                raise ValueError(f"vehicle {v.id}: unknown start location {v.start_location!r}")
        for d in self.deliveries:
            if d.pickup is not None and d.pickup.location not in ids:
                raise ValueError(f"delivery {d.id}: unknown pickup location {d.pickup.location!r}")
            if d.location not in ids:
                raise ValueError(f"delivery {d.id}: unknown location {d.location!r}")
            if d.window_end < d.window_start:
                raise ValueError(f"delivery {d.id}: window ends before it opens")
            if d.size <= 0:
                raise ValueError(f"delivery {d.id}: size must be positive")
        for c in self.closures:
            if c.a not in ids or c.b not in ids:
                raise ValueError(f"closure {c.a}-{c.b}: unknown location")
        for a in ids:
            for b in ids:
                if a != b and b not in self.matrix.get(a, {}):
                    raise ValueError(f"travel matrix is missing {a} -> {b}")
        return self

    def delivery(self, delivery_id: str) -> Delivery:
        return next(d for d in self.deliveries if d.id == delivery_id)

    def vehicle(self, vehicle_id: str) -> Vehicle:
        return next(v for v in self.vehicles if v.id == vehicle_id)


class Stop(BaseModel):
    """One visit. kind "pickup" collects the parcel `delivery_id`; kind "delivery" drops it.
    `idle` is time the vehicle sat at its previous location before leaving (only after a
    replan, when a vehicle had nothing to do until now)."""

    delivery_id: str
    location: str
    kind: Literal["delivery", "pickup"] = "delivery"
    idle: float = 0.0
    arrival: float
    wait: float
    service_start: float
    departure: float
    load_after: int
    frozen: bool = False


class Route(BaseModel):
    vehicle_id: str
    start_location: str
    start_time: float
    initial_load: int
    stops: list[Stop]
    travel_minutes: float

    @property
    def delivery_ids(self) -> list[str]:
        return [s.delivery_id for s in self.stops if s.kind == "delivery"]


class Unplaced(BaseModel):
    delivery_id: str
    reason: str
    vehicle_id: str | None = None  # the running vehicle the parcel is still aboard, if any


class Plan(BaseModel):
    scenario: str
    routes: list[Route]
    unplaced: list[Unplaced]
    total_travel: float
    solver: str
    limits: list[str]
    as_of: float | None = None

    def route(self, vehicle_id: str) -> Route:
        return next(r for r in self.routes if r.vehicle_id == vehicle_id)


def hhmm(t: float) -> str:
    m = round(t)
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


def parse_hhmm(s: str) -> float:
    h, m = s.split(":")
    return int(h) * 60 + int(m)
