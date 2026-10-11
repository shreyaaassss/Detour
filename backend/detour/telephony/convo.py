"""Read an ElevenLabs conversation and say what it means for the offer.

Pure functions, so they can be tested against saved conversations. The decision normally comes from the agent's
`report_decision` tool call, which is recorded in the transcript even when the call to our server could not get through,
so polling is a safety net for the live webhook.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

DECISIONS = {"confirmed", "declined", "unclear"}
TOOL = "report_decision"


@dataclass
class Reading:
    state: str  # ringing | in_call | ended
    decision: str | None  # confirmed | declined | unclear
    how: str | None  # voice | keypad | None when not known
    answered: bool  # the person picked up


def _tool_params(item: dict[str, Any]) -> dict[str, Any] | None:
    for tc in item.get("tool_calls") or []:
        if tc.get("tool_name") == TOOL:
            raw = tc.get("params_as_json")
            try:
                return json.loads(raw) if isinstance(raw, str) else dict(raw or {})
            except (ValueError, TypeError):
                return {}
    return None


def read_conversation(conv: dict[str, Any]) -> Reading:
    status = conv.get("status")
    transcript = conv.get("transcript") or []
    user_turns = [t for t in transcript if t.get("role") == "user" and (t.get("message") or "").strip()]
    answered = bool(user_turns) or status in ("in-progress", "processing", "done")
    if status == "failed":
        answered = bool(user_turns)

    decision: str | None = None
    how: str | None = None
    for item in transcript:
        params = _tool_params(item)
        if params is not None:
            d = str(params.get("decision", "")).lower()
            decision = d if d in DECISIONS else "unclear"
            m = str(params.get("method", "")).lower()
            how = m if m in ("voice", "keypad") else None
            break

    last = (user_turns[-1].get("message") or "").strip() if user_turns else ""
    if decision is None and status in ("done", "failed") and last in ("1", "2"):
        # the agent ended without reporting, but the keypad answer is unambiguous: 1 accepts, 2 declines
        decision, how = ("confirmed" if last == "1" else "declined"), "keypad"
    if decision and how is None:
        how = "keypad" if last in ("1", "2") else "voice" if last else None

    if decision is not None:
        state = "ended"
    elif status in ("done", "failed"):
        state = "ended"
    elif status == "in-progress" or answered:
        state = "in_call"
    else:
        state = "ringing"
    return Reading(state, decision, how, answered)
