"""Interpret a report: the language model if there is one, the rule-based reader always as a check and a fallback."""

from __future__ import annotations

import logging

from detour.engine.models import Scenario
from detour.parsing.llm import Reader, from_llm
from detour.parsing.rules import read_by_rules
from detour.parsing.types import Disruption, Issue, ParseResult

log = logging.getLogger("detour.parsing")
MAX_CHARS = 1000


def _signature(d: Disruption) -> tuple:
    kind = d.type
    if kind == "road_closure":
        return (kind, frozenset({d.a, d.b}))
    if kind == "vehicle_failure":
        return (kind, d.vehicle_id, d.location)
    return (kind, d.location, d.pickup_location)


def interpret(text: str, sc: Scenario, now: float, llm: Reader | None = None, source: str = "text") -> ParseResult:
    text = (text or "").strip()
    known = [{"id": x.id, "name": x.name} for x in sc.locations]
    if not text:
        return ParseResult(False, "rules", issues=[Issue("unclear", "Write what happened.")], known_locations=known)
    if len(text) > MAX_CHARS:
        return ParseResult(
            False,
            "rules",
            issues=[Issue("unclear", f"That is too long. Keep it under {MAX_CHARS} characters.")],
            known_locations=known,
        )

    rules = read_by_rules(text, sc, now)
    result = rules
    if llm is not None:
        try:
            raw = llm.read(text, sc, now)
        except Exception as e:  # network, timeout, bad key, malformed output: never fatal
            log.warning("language model unavailable: %s", type(e).__name__)
            rules.llm_error = type(e).__name__
            rules.warnings.append("The language model was unavailable, so the rule-based reader was used.")
        else:
            model = from_llm(raw, text, sc, now)
            model.model = llm.model
            if model.ok:
                result = model
                if (
                    rules.ok
                    and rules.disruption
                    and model.disruption
                    and _signature(rules.disruption) != _signature(model.disruption)
                ):
                    # two readers disagree: trust the strict one, and show what the model thought
                    result = rules
                    rules.warnings.append(f"The language model read it differently: {model.summary}")
                    rules.model = None
            elif rules.ok:
                rules.warnings.append("The language model could not read this, but the rule-based reader could.")
            else:
                result = model if model.issues else rules
    if result.disruption is not None:
        result.disruption = result.disruption.model_copy(update={"source": source})
    return result
