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
