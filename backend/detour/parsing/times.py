"""Clock times and durations in plain English text. Everything is minutes since midnight."""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORDS = {
    "the": 1,
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "half": 0.5,
    "couple": 2,
}
_UNIT = r"(hours?|hrs?|h|minutes?|mins?|m)\b"
_NUM = r"(\d+(?:\.\d+)?|the|a|an|one|two|three|four|five|six|half an?|a couple of)"


@dataclass(frozen=True)
class Clock:
    minutes: float
    start: int  # where it sits in the text, to keep reading order
    end: int
    explicit_period: bool  # the text said am or pm (or used 24-hour form), so there is no guess in it


def _resolve(hour: int, minute: int, meridiem: str | None, now: float) -> tuple[float | None, bool]:
    if minute > 59:
        return None, False
    if meridiem:
        if not 1 <= hour <= 12:
            return None, False
        h = hour % 12 + (12 if meridiem.startswith("p") else 0)
        return h * 60 + minute, True
    if hour > 23:
        return None, False
    if hour >= 13 or hour == 0:
        return hour * 60 + minute, True  # 24-hour form
    # 1 to 12 with no am or pm: take the reading that is not already in the past
    morning = (hour % 12) * 60 + minute
    afternoon = morning + 720
    if morning >= now - 1:
        return morning, False
    return afternoon, False


def clock_times(text: str, now: float) -> list[Clock]:
    t = text.lower()
    out: list[Clock] = []
    taken: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= x or a >= y for x, y in taken)

    for m in re.finditer(r"(?<![\d:.])(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)?(?!\d)", t):
        mer = m.group(3)
        minutes, explicit = _resolve(int(m.group(1)), int(m.group(2)), mer.replace(".", "") if mer else None, now)
        if minutes is not None and free(m.start(), m.end()):
            out.append(Clock(minutes, m.start(), m.end(), explicit or ":" in m.group(0) and int(m.group(1)) >= 13))
            taken.append((m.start(), m.end()))
    for m in re.finditer(r"(?<![\d:.])(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)(?![a-z])", t):
        minutes, explicit = _resolve(int(m.group(1)), 0, m.group(2).replace(".", ""), now)
        if minutes is not None and free(m.start(), m.end()):
            out.append(Clock(minutes, m.start(), m.end(), explicit))
            taken.append((m.start(), m.end()))
    part = r"(?:in the (afternoon|evening|morning)|(tonight|at night))"
    for m in re.finditer(rf"(?<![\d:.])(\d{{1,2}})(?:[:.](\d{{2}}))?\s*{part}", t):
        mer = "am" if m.group(3) == "morning" else "pm"
        minutes, explicit = _resolve(int(m.group(1)), int(m.group(2) or 0), mer, now)
        if minutes is not None and free(m.start(), m.end()):
            out.append(Clock(minutes, m.start(), m.end(), explicit))
            taken.append((m.start(), m.end()))
    for m in re.finditer(r"\b(\d{1,2})\s*o'?clock\b", t):
        minutes, explicit = _resolve(int(m.group(1)), 0, None, now)
        if minutes is not None and free(m.start(), m.end()):
            out.append(Clock(minutes, m.start(), m.end(), explicit))
            taken.append((m.start(), m.end()))
    return sorted(out, key=lambda c: c.start)


def _amount(word: str) -> float:
    w = word.strip().lower()
    if w in ("a couple of",):
        return 2
    if w.startswith("half"):
        return 0.5
    try:
        return float(w)
    except ValueError:
        return float(_WORDS.get(w, 0))


def _to_minutes(n: float, unit: str) -> float:
    return n * 60 if unit.startswith("h") else n


def duration_after(text: str, *prefixes: str) -> float | None:
    """A length of time introduced by one of the prefixes, e.g. 'for 2 hours', 'within 90 minutes'."""
    t = text.lower()
    for p in prefixes:
        m = re.search(rf"\b{p}\s+(?:the\s+next\s+|next\s+|another\s+|about\s+|around\s+)?{_NUM}\s*{_UNIT}", t)
        if m:
            n = _amount(m.group(1))
            if n > 0:
                return _to_minutes(n, m.group(2))
    return None


def mentions_now(text: str) -> bool:
    return re.search(r"\b(right now|just now|just|now|currently|at the moment|immediately)\b", text.lower()) is not None


def allowed_times(text: str, now: float) -> set[float]:
    """Every clock time that can honestly be read out of the text: a time written in it, now, or a stated
    length of time from one of those. Used to flag times a model has made up."""
    base = {now, *(c.minutes for c in clock_times(text, now))}
    lengths: set[float] = set()
    for m in re.finditer(rf"{_NUM}\s*{_UNIT}", text.lower()):
        n = _amount(m.group(1))
        if n > 0:
            lengths.add(_to_minutes(n, m.group(2)))
    return base | {b + d for b in base for d in lengths}
