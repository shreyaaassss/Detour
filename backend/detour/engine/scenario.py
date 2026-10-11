"""Scenario loading (JSON, CSV folder) and the built-in demo scenario (FR-1)."""
from __future__ import annotations

import csv
import math
from pathlib import Path

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
                a=r["a"], b=r["b"], start=_time(r["start"]), end=_time(r["end"]),
                added_minutes=float(r.get("added_minutes") or 0), multiplier=float(r.get("multiplier") or 1),
            )
            for r in rows("closures.csv")
        ]
        if (f / "closures.csv").exists()
        else []
    )
    return Scenario(
        name=name, depot=depot, day_start=_time(day_start), locations=locations,
        vehicles=vehicles, deliveries=deliveries, matrix=matrix, closures=closures,
    )


def demo_scenario() -> Scenario:
    """Fictional Pune scenario. Day starts 13:00 so the 14:00 to 15:00 rescue story fits."""
    locs = [
        Location(id="depot", name="Swargate Depot", x=50, y=30),
        Location(id="hadapsar", name="Hadapsar", x=78, y=40),
        Location(id="kothrud", name="Kothrud Clinic", x=18, y=50),
        Location(id="baner", name="Baner", x=20, y=85),
        Location(id="aundh", name="Aundh", x=30, y=72),
        Location(id="shivaji", name="Shivajinagar", x=45, y=62),
        Location(id="viman", name="Viman Nagar", x=80, y=78),
        Location(id="kharadi", name="Kharadi", x=95, y=68),
        Location(id="katraj", name="Katraj", x=48, y=5),
        Location(id="camp", name="Camp", x=62, y=48),
        Location(id="wakad", name="Wakad", x=5, y=92),
    ]
    vehicles = [
        Vehicle(id="V1", capacity=60, start_location="depot", driver="Arjun"),
        Vehicle(id="V2", capacity=60, start_location="depot", driver="Ravi"),
        Vehicle(id="V3", capacity=50, start_location="depot", driver="Sana"),
        Vehicle(id="V4", capacity=50, start_location="depot", driver="Meera"),
        Vehicle(id="V5", capacity=40, start_location="depot", driver="Imran"),
    ]

    def d(i: str, loc: str, size: int, ws: str, we: str, svc: float = 5, prio: bool = False) -> Delivery:
        return Delivery(id=i, location=loc, size=size, window_start=parse_hhmm(ws),
                        window_end=parse_hhmm(we), service_time=svc, priority=prio)

    deliveries = [
        d("D1", "hadapsar", 20, "13:30", "15:30"),
        d("D2", "camp", 15, "13:00", "15:00"),
        d("D3", "katraj", 25, "13:30", "16:00"),
        d("D4", "shivaji", 10, "14:00", "15:30"),
        d("D5", "viman", 20, "14:00", "16:00"),
        d("D6", "kharadi", 15, "14:30", "16:30"),
        d("D7", "kothrud", 10, "14:00", "15:00", 5, True),
        d("D8", "aundh", 15, "14:00", "16:00"),
        d("D9", "baner", 20, "14:30", "15:15"),
        d("D10", "wakad", 25, "15:00", "17:00"),
        d("D11", "camp", 10, "14:00", "16:00"),
        d("D12", "hadapsar", 15, "15:00", "17:00"),
    ]
    return Scenario(
        name="Pune demo", depot="depot", day_start=parse_hhmm("13:00"), locations=locs,
        vehicles=vehicles, deliveries=deliveries, matrix=derive_matrix(locs),
    )
