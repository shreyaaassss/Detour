"""Customer messages, drafted from the plan's facts for the dispatcher to approve (FR-12).

Every time and place comes from the engine's diff; there is no generated wording to get wrong, and no
internal ids, vehicle names or driver names reach a customer.
"""

from __future__ import annotations

from typing import Any

from detour.engine.models import hhmm


def _cause(kinds: list[str]) -> str:
    phrases = {
        "vehicle_failure": "a vehicle breakdown",
        "road_closure": "a road closure",
        "urgent_delivery": "an urgent delivery we had to fit in",
    }
    seen = [phrases[k] for k in dict.fromkeys(kinds) if k in phrases]
    if not seen:
        return "a change to our plan"
    return seen[0] if len(seen) == 1 else ", ".join(seen[:-1]) + " and " + seen[-1]


def drafts(session: Any) -> list[dict[str, Any]]:
    diff = session.diff()
    if diff is None:
        return []
    sc = session.scenario
    why = _cause([a["type"] for a in session.applied])
    out: list[dict[str, Any]] = []
    for c in diff.changes:
        d = sc.delivery(c.delivery_id)
        place = next(loc.name for loc in sc.locations if loc.id == d.location)
        window = f"{hhmm(d.window_start)} to {hhmm(d.window_end)}"
        if c.status == "moved" and not c.completed:
            if c.old_service is not None and c.new_service is not None and abs(c.new_service - c.old_service) < 1:
                continue
            text = (
                f"Hello, this is DeTour about your delivery to {place}. Because of {why}, it will now arrive "
                f"around {hhmm(c.new_service)} instead of {hhmm(c.old_service)}. Your delivery window is {window}. "
                "Sorry for the change."
            )
        elif c.status == "broken":
            text = (
                f"Hello, this is DeTour about your delivery to {place}. Because of {why}, we cannot deliver it "
                f"within your window ({window}). We are sorry. We will contact you to arrange a new time."
            )
        elif c.status == "new":
            text = (
                f"Hello, this is DeTour. Your urgent delivery to {place} is on its way and is expected around "
                f"{hhmm(c.new_service)}."
            )
        else:
            continue
        out.append(
            {
                "delivery_id": c.delivery_id,
                "status": c.status,
                "place": place,
                "text": text,
                "approved": session.approved_messages.get(c.delivery_id) == text,
            }
        )
    order = {"broken": 0, "moved": 1, "new": 2}
    return sorted(out, key=lambda m: (order[m["status"]], m["delivery_id"]))
