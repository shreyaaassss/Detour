from __future__ import annotations

from collections.abc import Iterable

from .models import Closure


class TravelModel:
    """Time-dependent travel. A closure inflates a leg only when the departure
    time falls inside its [start, end) window (FR-3)."""

    def __init__(self, matrix: dict[str, dict[str, float]], closures: Iterable[Closure] = ()):
        self.matrix = matrix
        self.closures = tuple(closures)

    def base(self, a: str, b: str) -> float:
        return 0.0 if a == b else self.matrix[a][b]

    def travel(self, a: str, b: str, departure: float) -> float:
        t = self.base(a, b)
        if a == b:
            return t
        for c in self.closures:
            if {c.a, c.b} == {a, b} and c.start <= departure < c.end:
                t = t * c.multiplier + c.added_minutes
        return t

    def with_closures(self, closures: Iterable[Closure]) -> TravelModel:
        return TravelModel(self.matrix, (*self.closures, *closures))
