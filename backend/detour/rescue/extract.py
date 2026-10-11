"""Pull a breakdown report out of free text, with no AI. Used when voice or the language model is
unavailable, and as the check on whatever they return: a place must be on the known list.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from detour.engine.models import Scenario

BREAKDOWN_WORDS = [
    # English
    "broke down",
    "broken down",
    "breakdown",
    "break down",
    "broken",
    "stuck",
    "won't start",
    "wont start",
    "not starting",
    "engine",
    "puncture",
    "flat tyre",
    "flat tire",
    "accident",
    "stalled",
    "overheat",
    # Hindi
    "खराब",
    "ख़राब",
    "बंद हो",
    "पंक्चर",
    "पंचर",
    "टायर",
    "इंजन",
    "फंस",
    "रुक गई",
    "रुक गया",
    # Marathi
    "बिघडली",
    "बिघाड",
    "बंद पडली",
    "बंद पडला",
    "इंजिन",
    "अडकली",
    "थांबली",
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).casefold().strip()


@dataclass
class Extraction:
    location_ids: list[str] = field(default_factory=list)
    breakdown: bool = False

    @property
    def location_id(self) -> str | None:
        return self.location_ids[0] if len(self.location_ids) == 1 else None


def _mentions(text: str, name: str) -> bool:
    n = _norm(name)
    if not n:
        return False
    if n.isascii():  # whole words, so "camp" does not match "campus"
        return re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text) is not None
    return n in text


def extract(text: str, scenario: Scenario) -> Extraction:
    t = _norm(text)
    found: list[str] = []
    for loc in scenario.locations:
        names = [loc.name, *loc.aliases]
        if any(_mentions(t, n) for n in names) and loc.id not in found:
            found.append(loc.id)
    breakdown = any(_norm(w) in t for w in BREAKDOWN_WORDS)
    return Extraction(found, breakdown)


def places_in_order(text: str, scenario: Scenario) -> list[str]:
    """Known places mentioned in the text, in the order they first appear."""
    t = _norm(text)
    found: list[tuple[int, str]] = []
    for loc in scenario.locations:
        best = None
        for name in [loc.name, *loc.aliases]:
            n = _norm(name)
            if not n:
                continue
            m = re.search(rf"(?<!\w){re.escape(n)}(?!\w)", t) if n.isascii() else re.search(re.escape(n), t)
            if m and (best is None or m.start() < best):
                best = m.start()
        if best is not None:
            found.append((best, loc.id))
    return [i for _, i in sorted(found)]


def mentions(text: str, scenario: Scenario, loc_id: str) -> bool:
    """True if the text really names this place (by its name or an alias)."""
    return loc_id in places_in_order(text, scenario)
