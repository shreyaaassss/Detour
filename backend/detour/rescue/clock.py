"""The simulated time of day, in minutes since midnight.

The 60-second offer timers run in real seconds, but plans are timed in simulated minutes. By default the
simulated clock is paused, so a demo gives the same numbers on every run. In live mode it advances.
"""

from __future__ import annotations

import time
from collections.abc import Callable


class SimClock:
    def __init__(self, sim_minutes: float = 0.0, speed: float = 0.0, wall: Callable[[], float] = time.time):
        self._wall = wall
        self._sim = sim_minutes
        self._anchor = wall()
        self.speed = speed  # simulated minutes per real minute; 0 means paused

    def now(self) -> float:
        return self._sim + (self._wall() - self._anchor) / 60.0 * self.speed

    def set(self, sim_minutes: float | None = None, speed: float | None = None) -> None:
        current = self.now()
        self._anchor = self._wall()
        self._sim = current if sim_minutes is None else sim_minutes
        if speed is not None:
            self.speed = max(0.0, speed)

    @property
    def live(self) -> bool:
        return self.speed > 0
