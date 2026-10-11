"""Three-role dry run against a running server: stranded driver (Ravi), head, rescue driver(s), plus the dispatcher's
audit view. Each role acts only through its own screen's API calls, and a listener per role watches the event stream,
as three phones would. Run the server with short timers and no outside services:

    DETOUR_PUSH_TIMEOUT=3 DETOUR_RING_TIMEOUT=3 DETOUR_CONVERSATION_LIMIT=4 ELEVENLABS_API_KEY= OPENAI_API_KEY= \
        uv run uvicorn detour.main:app --port 8000
    uv run python scripts/rehearsal.py
"""

from __future__ import annotations

import sys
import threading
import time

import httpx

BASE = "http://localhost:8000"
http = httpx.Client(base_url=BASE, timeout=10)
failures: list[str] = []
seen: dict[str, list[str]] = {"driver": [], "head": [], "rescuer": []}


def check(ok: bool, what: str) -> None:
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        failures.append(what)


def listen(role: str, stop: threading.Event) -> None:
    try:
        with httpx.stream("GET", BASE + "/events", timeout=None) as r:
            for line in r.iter_lines():
                if stop.is_set():
                    return
                if line.startswith("event:"):
                    seen[role].append(line[6:].strip())
    except httpx.HTTPError:
        pass


def j(method: str, path: str, **kw):
    r = http.request(method, path, **kw)
    return r.status_code, (r.json() if r.content else {})


def wait_state(iid: str, want: set[str], seconds: float = 12) -> str:
    end, st = time.time() + seconds, ""
    while time.time() < end:
        st = j("GET", f"/incidents/{iid}")[1]["incident"]["state"]
        if st in want:
            return st
        time.sleep(0.2)
    return st


def start_rescue(shortlist=("V4", "V3", "V5")) -> str:
    _, rep = j("POST", "/incidents/report", json={"driver": "Ravi", "transcript": "broke down near Hadapsar"})
    iid = rep["incident"]["id"]
    j("POST", f"/incidents/{iid}/confirm", json={"confirmed": True})
    v = j("GET", f"/incidents/{iid}/proposal")[1]["proposal"]["plan_version"]
    code, _ = j(
        "POST",
        f"/incidents/{iid}/approve",
        json={"approved_by": "head", "shortlist": list(shortlist), "proposal_version": v},
    )
    check(code == 200, "head approves a shortlist of three")
    return iid


def offer_of(iid: str) -> dict:
    return j("GET", f"/incidents/{iid}")[1]["incident"]["active_offer"] or {}


def valid() -> bool:
    return j("GET", "/state")[1]["report"]["valid"]


def main() -> int:
    stop = threading.Event()
    for role in seen:
        threading.Thread(target=listen, args=(role, stop), daemon=True).start()
    time.sleep(0.5)

    print("Scene 1: the rescue driver accepts in the app")
    j("POST", "/reset")
    iid = start_rescue()
    off = offer_of(iid)
    check(off.get("driver") == "Meera" and off.get("channel") == "push", "Meera (top of the list) sees a push offer")
    code, _ = j("POST", f"/offers/{off['id']}/respond", json={"response": "accept", "by": "Meera"})
    check(code == 200 and wait_state(iid, {"COMMITTED"}) == "COMMITTED", "accepting commits the rescue")
    check(valid(), "the plan is valid after the rescue")
    code, _ = j("POST", f"/offers/{off['id']}/respond", json={"response": "accept", "by": "Meera"})
    check(code == 409, "a second tap is refused")

    print("Scene 2: no answer in the app, then the call escalation")
    j("POST", "/reset")
    iid = start_rescue()
    check(wait_state(iid, {"CALL_ESCALATED"}) == "CALL_ESCALATED", "after the push timeout the call is escalated")
    call = offer_of(iid)
    check(call.get("channel") == "call", "the active offer is now a call")
    code, _ = j("POST", f"/offers/{call['id']}/respond", json={"response": "accept", "via": "tap"})
    check(code == 422, "the app cannot answer a call offer")
    j("POST", "/telephony/webhook", json={"offer_id": call["id"], "outcome": "answered"})
    j("POST", "/telephony/webhook", json={"offer_id": call["id"], "outcome": "confirmed"})
    check(wait_state(iid, {"COMMITTED"}) == "COMMITTED", "pressing 1 on the call commits the rescue")
    check(valid(), "the plan is valid after a call-confirmed rescue")

    print("Scene 3: decline, then ring with no answer, then the next driver takes it")
    j("POST", "/reset")
    iid = start_rescue()
    off = offer_of(iid)
    j("POST", f"/offers/{off['id']}/respond", json={"response": "decline", "by": "Meera"})
    off = offer_of(iid)
    check(off.get("driver") == "Sana", "a decline moves the offer to Sana")
    check(wait_state(iid, {"CALL_ESCALATED"}) == "CALL_ESCALATED", "Sana does not answer: she is called")
    moved = wait_state(iid, {"OFFER_PUSHED"}, 8) == "OFFER_PUSHED" and offer_of(iid).get("driver") == "Imran"
    check(moved, "the ring times out: Imran is next")
    off = offer_of(iid)
    j("POST", f"/offers/{off['id']}/respond", json={"response": "accept", "by": "Imran"})
    check(wait_state(iid, {"COMMITTED"}) == "COMMITTED" and valid(), "Imran accepts and the plan stays valid")

    print("Scene 4: everyone declines")
    j("POST", "/reset")
    iid = start_rescue(("V4", "V3"))
    for who in ("Meera", "Sana"):
        off = offer_of(iid)
        j("POST", f"/offers/{off['id']}/respond", json={"response": "decline", "by": who})
    check(wait_state(iid, {"EXHAUSTED"}) == "EXHAUSTED", "nobody accepts: the rescue is exhausted, not guessed")
    check(valid(), "the plan is still valid and no one was promised help")

    print("Scene 5: audit trail and screens")
    code, v = j("GET", "/audit/verify")
    check(code == 200 and v.get("valid", v.get("ok")) is True, "the audit chain verifies")
    for role, evs in seen.items():
        check(len(evs) > 0, f"the {role} screen received live updates ({len(evs)} events)")
    stop.set()
    print(f"\n{'PASSED' if not failures else 'FAILED: ' + str(len(failures))}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
