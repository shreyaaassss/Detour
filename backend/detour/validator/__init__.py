"""Independent plan validator (FR-13, FR-14).

Deliberately shares no code with detour.engine: it takes plain dicts (for example
`scenario.model_dump()` and `plan.model_dump()`), re-times every route from scratch
and checks every hard rule. A test fails the build if this package imports the engine.
"""

from .check import Report, Violation, validate

__all__ = ["Report", "Violation", "validate"]
