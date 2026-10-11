"""Scenario loading (JSON, CSV folder) and the built-in demo scenario (FR-1)."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from .disruptions import RoadClosure, UrgentDelivery, VehicleFailure
from .models import Closure, Delivery, Location, Scenario, Vehicle, parse_hhmm

MIN_PER_UNIT = 0.5  # simulated pace: 0.5 minute per grid unit


def derive_matrix(locations: list[Location]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for a in locations:
        out[a.id] = {}
        for b in locations:
            if a.id != b.id:
                out[a.id][b.id] = max(1, round(math.hypot(a.x - b.x, a.y - b.y) * MIN_PER_UNIT))
    return out


def load_json(path: str | Path) -> Scenario:
    return Scenario.model_validate_json(Path(path).read_text())


def _time(s: str) -> float:
    return parse_hhmm(s) if ":" in s else float(s)


def load_csv_dir(folder: str | Path, name: str, depot: str, day_start: str = "08:00") -> Scenario:
    """Folder with locations.csv, vehicles.csv, deliveries.csv and optional matrix.csv, closures.csv."""
    f = Path(folder)

    def rows(fn: str) -> list[dict[str, str]]:
        with open(f / fn, newline="") as fh:
            return list(csv.DictReader(fh))

    locations = [Location(id=r["id"], name=r["name"], x=float(r["x"]), y=float(r["y"])) for r in rows("locations.csv")]
    vehicles = [
        Vehicle(
            id=r["id"],
            capacity=int(r["capacity"]),
            start_location=r.get("start_location") or depot,
            driver=r.get("driver") or None,
        )
        for r in rows("vehicles.csv")
    ]
    deliveries = [
        Delivery(
            id=r["id"],
            location=r["location"],
            size=int(r["size"]),
            window_start=_time(r["window_start"]),
            window_end=_time(r["window_end"]),
            service_time=float(r.get("service_time") or 5),
            priority=(r.get("priority", "").lower() in {"1", "true", "yes"}),
        )
        for r in rows("deliveries.csv")
    ]
    if (f / "matrix.csv").exists():
        matrix: dict[str, dict[str, float]] = {}
        for r in rows("matrix.csv"):
            matrix.setdefault(r["from"], {})[r["to"]] = float(r["minutes"])
    else:
        matrix = derive_matrix(locations)
    closures = (
        [
            Closure(
                a=r["a"],
                b=r["b"],
                start=_time(r["start"]),
                end=_time(r["end"]),
                added_minutes=float(r.get("added_minutes") or 0),
                multiplier=float(r.get("multiplier") or 1),
            )
            for r in rows("closures.csv")
        ]
        if (f / "closures.csv").exists()
        else []
    )
    return Scenario(
        name=name,
        depot=depot,
        day_start=_time(day_start),
        locations=locations,
        vehicles=vehicles,
        deliveries=deliveries,
        matrix=matrix,
        closures=closures,
    )


def demo_scenario() -> Scenario:
    """Fictional Pune scenario. The day starts at 13:00 so the 14:05 rescue story fits.

    Locations are placed so that, at 14:05, the four candidate rescuers are 10, 15, 18 and 27
    minutes from Hadapsar, and Hadapsar to Kothrud Clinic is 30 minutes (PRD section 7)."""
    locs = [
        Location(id="depot", name="Swargate Depot", x=50, y=30),
        Location(id="hadapsar", name="Hadapsar", x=78, y=40),
        Location(id="kothrud", name="Kothrud Clinic", x=18, y=50),
        Location(id="aundh", name="Aundh", x=30, y=72),
        Location(id="baner", name="Baner", x=20, y=85),
        Location(id="wanowrie", name="Wanowrie", x=58, y=40),
        Location(id="kondhwa", name="Kondhwa", x=48, y=40),
        Location(id="katraj", name="Katraj", x=42, y=40),
        Location(id="shivaji", name="Shivajinagar", x=24, y=40),
        Location(id="viman", name="Viman Nagar", x=80, y=78),
        Location(id="kharadi", name="Kharadi", x=95, y=68),
        Location(id="camp", name="Camp", x=62, y=48),
    ]
    vehicles = [
        Vehicle(id="V1", capacity=60, start_location="depot", driver="Arjun"),
        Vehicle(id="V2", capacity=60, start_location="depot", driver="Ravi"),
        Vehicle(id="V3", capacity=50, start_location="depot", driver="Sana"),
        Vehicle(id="V4", capacity=50, start_location="depot", driver="Meera"),
        Vehicle(id="V5", capacity=40, start_location="depot", driver="Imran"),
    ]

    def d(i: str, loc: str, size: int, ws: str, we: str, svc: float = 5, prio: bool = False) -> Delivery:
        return Delivery(
            id=i,
            location=loc,
            size=size,
            window_start=parse_hhmm(ws),
            window_end=parse_hhmm(we),
            service_time=svc,
            priority=prio,
        )

    deliveries = [
        d("D1", "hadapsar", 10, "13:45", "14:15"),
        d("D2", "wanowrie", 10, "13:30", "14:00"),
        d("D3", "kondhwa", 10, "13:30", "14:00"),
        d("D4", "katraj", 8, "13:30", "14:00"),
        d("D5", "shivaji", 10, "13:30", "14:00"),
        d("D6", "viman", 10, "16:30", "18:30"),
        d("D7", "kothrud", 15, "14:00", "15:00", 5, True),  # urgent medicine for the clinic
        d("D8", "aundh", 12, "14:30", "16:30"),
        d("D9", "baner", 10, "14:30", "14:55"),
        d("D10", "viman", 15, "16:00", "18:00"),
        d("D11", "kharadi", 12, "16:00", "18:00"),
        d("D12", "camp", 10, "16:00", "18:00"),
    ]
    return Scenario(
        name="Pune demo",
        depot="depot",
        day_start=parse_hhmm("13:00"),
        locations=locs,
        vehicles=vehicles,
        deliveries=deliveries,
        matrix=derive_matrix(locs),
    )


# Hand-assigned demo baseline so the story reproduces on every run. The solver can plan
# the same scenario on its own (POST /plan); this is the plan shown when the demo loads.
DEMO_BASELINE: dict[str, list[str]] = {
    "V1": ["D5", "D6"],
    "V2": ["D1", "D7", "D8", "D9"],
    "V3": ["D3", "D11"],
    "V4": ["D2", "D10"],
    "V5": ["D4", "D12"],
}


def demo_presets() -> dict[str, RoadClosure | VehicleFailure | UrgentDelivery]:
    """One-click demo disruptions. Each is applied to DEMO_BASELINE and gives the same result every run."""
    t = parse_hhmm
    return {
        # Ravi (V2) breaks down at Hadapsar with D7, D8 and D9 aboard (PRD section 7).
        "vehicle_failure": VehicleFailure(vehicle_id="V2", time=t("14:05"), location="hadapsar"),
        # Kothrud-Aundh slows by 25 min from 14:00 to 16:00; V2's route to Aundh and Baner is hit.
        "road_closure": RoadClosure(
            a="kothrud", b="aundh", start=t("14:00"), end=t("16:00"), added_minutes=25, reported_at=t("14:00")
        ),
        # A parcel from the depot to Wanowrie, wanted within the hour.
        "urgent_delivery": UrgentDelivery(
            id="D13", location="wanowrie", size=8, window_start=t("14:10"), window_end=t("15:00"), time=t("14:05")
        ),
    }
