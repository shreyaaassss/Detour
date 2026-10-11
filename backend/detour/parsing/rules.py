"""Read a report without any AI. Plain patterns for the three disruptions.

It is strict on purpose: it asks for what is missing instead of assuming it, and it only ever uses places,
vehicles and times that the text really contains.
"""

from __future__ import annotations

import re

from detour.engine.disruptions import DisruptionError, RoadClosure, UrgentDelivery, VehicleFailure, validate_disruption
from detour.engine.models import Scenario, hhmm
from detour.parsing.summary import summarise
from detour.parsing.times import Clock, clock_times, duration_after
from detour.parsing.types import Issue, ParseResult
from detour.rescue.extract import BREAKDOWN_WORDS, places_in_order

CLOSURE_WORDS = [
    "closed",
    "closure",
    "blocked",
    "blockage",
    "jam",
    "traffic",
    "slow",
    "diversion",
    "waterlog",
    "flood",
    "bridge",
    "roadwork",
    "road work",
    "construction",
    "road is shut",
    "shut",
    "adds",
    "slower",
]
FAILURE_WORDS = [*BREAKDOWN_WORDS, "failed", "died", "dead", "conked", "won't move"]
URGENT_WORDS = [
    "urgent",
    "rush",
    "asap",
    "emergency",
    "new delivery",
    "extra delivery",
    "additional delivery",
    "add a delivery",
    "add delivery",
    "needs delivering",
    "priority delivery",
]


def _has(text: str, words: list[str]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(w)}", text) for w in words)


def _known(sc: Scenario) -> list[dict[str, str]]:
    return [{"id": loc.id, "name": loc.name} for loc in sc.locations]


def _before(text: str, c: Clock, width: int = 14) -> str:
    return text[max(0, c.start - width) : c.start].lower()


def read_by_rules(text: str, sc: Scenario, now: float) -> ParseResult:
    t = text.lower()
    res = ParseResult(ok=False, method="rules", known_locations=_known(sc))
    kinds = {
        "road_closure": _has(t, CLOSURE_WORDS),
        "vehicle_failure": _has(t, FAILURE_WORDS),
        "urgent_delivery": _has(t, URGENT_WORDS),
    }
    hit = [k for k, v in kinds.items() if v]
    if len(hit) > 1:
        res.issues.append(Issue("several", "This sounds like more than one change. Describe them one at a time."))
        return res
    if not hit:
        res.issues.append(
            Issue(
                "unclear",
                "I could not tell what changed. Say whether a road is closed or slow, a vehicle broke down, "
                "or an urgent delivery was added.",
            )
        )
        return res
    kind = hit[0]
    places = places_in_order(text, sc)
    clocks = clock_times(text, now)

    d = None
    if kind == "road_closure":
        d = _closure(res, t, text, sc, now, places, clocks)
    elif kind == "vehicle_failure":
        d = _failure(res, t, sc, now, places, clocks)
    else:
        d = _urgent(res, t, sc, now, places, clocks)
    if d is None or res.issues:
        return res
    try:
        validate_disruption(sc, d)
    except DisruptionError as e:
        res.issues.append(Issue("invalid", str(e)))
        return res
    res.ok, res.disruption, res.summary = True, d, summarise(d, sc, now)
    for c in clocks:  # a time with no am, pm or 24-hour form is a reading, so say which one was taken
        if not c.explicit_period:
            res.warnings.append(f"I read '{text[c.start : c.end].strip()}' as {hhmm(c.minutes)}.")
    return res


def _place_issue(res: ParseResult, places: list[str], want: int, what: str) -> bool:
    """Record why the places are not what is needed. Returns True if they are fine."""
    if len(places) == want:
        return True
    if not places:
        res.issues.append(
            Issue(
                "unknown_place",
                f"I could not find a place I know for {what}. Choose from the known places.",
                "location",
            )
        )
    elif len(places) < want:
        res.issues.append(Issue("missing", f"I found only one place, but {what} needs {want}.", "location"))
    else:
        res.issues.append(
            Issue("several", f"I found {len(places)} places but {what} needs {want}. Which ones?", "location")
        )
    return False


def _closure(res, t, text, sc, now, places, clocks):
    ok = _place_issue(res, places, 2, "a road closure")
    start = end = None
    dur = duration_after(t, "for", "lasting", "next")
    ahead = duration_after(t, "in")
    if len(clocks) >= 2:
        start, end = clocks[0].minutes, clocks[1].minutes
    elif len(clocks) == 1:
        c = clocks[0]
        if re.search(r"(until|till|upto|up to|by|before)\s*$", _before(t, c, 10)):
            start, end = now, c.minutes
        else:
            start = c.minutes
            end = start + dur if dur else None
    else:
        start = now + (ahead or 0)
        end = start + dur if dur else None
    if end is None:
        res.issues.append(
            Issue("missing", "Say when the slowdown ends, for example 'until 4 pm' or 'for 2 hours'.", "end")
        )
    elif start is not None and end <= start:
        res.issues.append(Issue("invalid", "The slowdown must end after it starts.", "end"))
    elif end <= now:
        res.issues.append(Issue("invalid", "That period has already ended.", "end"))

    added = mult = None
    m = re.search(
        r"(?:adds?|adding|add|\+|extra|slower by|delayed? (?:of|by)|slowed by)\s*(\d+)\s*(?:min|mins|minutes)\b", t
    ) or re.search(r"(\d+)\s*(?:min|mins|minutes)\s*(?:extra|more|longer|delay|added|slower)\b", t)
    if m:
        added = float(m.group(1))
    elif re.search(r"\b(twice as|double|doubles|doubled|2x|two times)\b", t):
        mult = 2.0
    elif re.search(r"\b(three times|3x|triple|tripled)\b", t):
        mult = 3.0
    if added is None and mult is None:
        res.issues.append(
            Issue("missing", "Say how much slower it is, for example 'adds 20 minutes' or 'twice as long'.", "effect")
        )
    if not ok or res.issues or start is None or end is None:
        return None
    return RoadClosure(
        a=places[0],
        b=places[1],
        start=start,
        end=end,
        added_minutes=added or 0,
        multiplier=mult or 1.0,
        reported_at=now,
        source="text",
    )


def _vehicle(res, t, sc) -> str | None:
    named = sorted({m.group(1) for m in re.finditer(r"\bv\s?-?(\d+)\b", t)}, key=int)
    known = {v.id for v in sc.vehicles}
    found = [f"V{n}" for n in named if f"V{n}" in known]
    for v in sc.vehicles:
        if v.driver and re.search(rf"(?<!\w){re.escape(v.driver.lower())}(?!\w)", t) and v.id not in found:
            found.append(v.id)
    if len(found) == 1:
        return found[0]
    roster = ", ".join(f"{v.id} ({v.driver})" if v.driver else v.id for v in sc.vehicles)
    if named and not found:
        res.issues.append(
            Issue("unknown_vehicle", f"I do not know vehicle V{named[0]}. The vehicles are {roster}.", "vehicle")
        )
    elif not found:
        res.issues.append(Issue("missing", "Say which vehicle, for example 'V2' or the driver's name.", "vehicle"))
    else:
        res.issues.append(
            Issue("several", f"I found more than one vehicle ({', '.join(found)}). Which one broke down?", "vehicle")
        )
    return None


def _failure(res, t, sc, now, places, clocks):
    vid = _vehicle(res, t, sc)
    ok = _place_issue(res, places, 1, "a breakdown")
    time = clocks[0].minutes if clocks else now
    if not ok or vid is None:
        return None
    return VehicleFailure(vehicle_id=vid, time=time, location=places[0], source="text")


def _urgent(res, t, sc, now, places, clocks):
    pickup = None
    if len(places) == 2 and re.search(r"\bfrom\b.*\bto\b", t):
        pickup, place = places[0], places[1]
        ok = True
    else:
        ok = _place_issue(res, places, 1, "an urgent delivery")
        place = places[0] if places else None
    m = re.search(r"(?:size|qty|quantity)\s*(?:of|is|:)?\s*(\d+)", t) or re.search(
        r"(\d+)\s*(?:units?|parcels?|boxes|packages?|kg|items?|cartons?)\b", t
    )
    size = int(m.group(1)) if m else None
    if size is None:
        res.issues.append(Issue("missing", "Say how big it is, for example 'size 8' or '8 parcels'.", "size"))
    ws, we = now, None
    if len(clocks) >= 2:
        ws, we = clocks[0].minutes, clocks[1].minutes
    elif len(clocks) == 1:
        we = clocks[0].minutes
    else:
        within = duration_after(t, "within", "in", "for")
        we = now + within if within else None
    if we is None:
        res.issues.append(Issue("missing", "Say the deadline, for example 'by 3 pm' or 'within 2 hours'.", "window"))
    elif we <= ws:
        res.issues.append(Issue("invalid", "The deadline must be after the delivery window opens.", "window"))
    existing = {d.id for d in sc.deliveries}
    n = len(existing) + 1
    while f"D{n}" in existing:
        n += 1
    mid = re.search(r"\b(d\d+)\b", t)
    did = mid.group(1).upper() if mid and mid.group(1).upper() not in existing else f"D{n}"
    if not ok or res.issues or place is None or size is None or we is None:
        return None
    return UrgentDelivery(
        id=did,
        location=place,
        size=size,
        window_start=ws,
        window_end=we,
        pickup_location=pickup,
        time=now,
        source="text",
    )
