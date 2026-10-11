from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from detour.engine.disruptions import RoadClosure, UrgentDelivery, VehicleFailure

Disruption = RoadClosure | VehicleFailure | UrgentDelivery


@dataclass
class Issue:
    code: str  # unknown_place, missing, several, unclear, invalid
    message: str
    field: str | None = None


@dataclass
class ParseResult:
    ok: bool
    method: str  # "llm" or "rules"
    disruption: Disruption | None = None
    summary: str | None = None
    model: str | None = None
    issues: list[Issue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    known_locations: list[dict[str, str]] = field(default_factory=list)
    llm_error: str | None = None  # the kind of failure if the language model could not be used

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "method": self.method,
            "model": self.model,
            "summary": self.summary,
            "disruption": self.disruption.model_dump() if self.disruption else None,
            "issues": [i.__dict__ for i in self.issues],
            "warnings": self.warnings,
            "known_locations": self.known_locations,
            "llm_error": self.llm_error,
        }
