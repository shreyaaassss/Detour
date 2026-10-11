"""The rescue state machine (PRD section 6).

    REPORTED -> DRIVER_CONFIRMED -> AWAITING_HEAD -> HEAD_APPROVED -> OFFER_PUSHED(i) -> CALL_ESCALATED(i)
        -> ACCEPTED(i) -> COMMITTED            or CANDIDATE_DECLINED(i) -> next, or EXHAUSTED

Rules this file enforces:
  - the plan does not change until a rescuer accepts and the result re-validates;
  - exactly one acceptance can win; a late tap or call is refused and logged;
  - the head approves an exact shortlist for an exact plan version, and any plan change voids it;
  - nobody is told help is coming until the assignment is committed.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from detour.engine.disruptions import VehicleFailure
from detour.engine.models import hhmm
from detour.rescue.extract import extract
from detour.rescue.models import (
    OFFERING,
    TERMINAL,
    HistoryItem,
    Incident,
    Notification,
    Offer,
    Proposal,
)
from detour.rescue.ranking import evaluate, pick_primary, rank, remaining_parcels
from detour.rescue.strings import LANGS, local_names, say, say_all
from detour.session import ApiError, Session


@dataclass
class RescueConfig:
    push_timeout: float = 60.0  # required by the PRD
    driver_confirm: float = 30.0
    head_response: float = 120.0
    ring_timeout: float = 25.0  # a phone that rings
    browser_conversation_limit: float = 150.0  # a browser call may include questions and answers
    browser_ring_timeout: float = 60.0  # no phone line: a person has to read the card, tap and allow the microphone
    conversation_limit: float = 45.0
    max_shortlist: int = 3
    max_reprompts: int = 3


class RescueService:
    def __init__(self, session: Session, cfg: RescueConfig | None = None, wall: Callable[[], float] = time.time):
        self.s = session
        self.cfg = cfg or RescueConfig()
        self.wall = wall
        self.incidents: dict[str, Incident] = {}
        self.offers: dict[str, Offer] = {}
        self.notes: list[Notification] = []
        self._note_seq = 0  # ids keep rising across a reset, so a screen asking for 'newer than N' never misses one
        self._committing: set[str] = set()
        self.calls: Any = None  # the phone service, when real calls are set up
        self._n_inc = 0
        self._n_off = 0
        session.on_change(self._plan_changed)

    # --- small helpers ----------------------------------------------------------------------
    def _log(self, actor: str, action: str, details: dict[str, Any]) -> None:
        self.s.log(actor, action, details)

    def _loc(self, loc_id: str | None) -> str:
        return next((loc.name for loc in self.s.scenario.locations if loc.id == loc_id), loc_id or "")

    def _place(self, loc_id: str | None) -> dict[str, str]:
        loc = next((x for x in self.s.scenario.locations if x.id == loc_id), None)
        return local_names(loc.name, loc.aliases) if loc else {"en": loc_id or ""}

    def _publish(self, kind: str, **data: Any) -> None:
        self.s.bus.publish({"type": kind, **data})

    def _set(self, inc: Incident, state: str, note: str = "") -> None:
        inc.state = state  # type: ignore[assignment]
        if note:
            inc.note = note
        inc.history.append(HistoryItem(wall=self.wall(), sim=self.s.sim_time, state=state, note=note))
        self._log("system", "incident_state", {"incident": inc.id, "state": state, "note": note})
        self._publish("incident", id=inc.id, state=state)

    def notify(self, to: str, kind: str, text: dict[str, str], inc: Incident | None = None, **data: Any) -> None:
        self._note_seq += 1
        n = Notification(
            id=self._note_seq,
            to=to,
            kind=kind,
            incident_id=inc.id if inc else None,
            text=text,
            wall=self.wall(),
            sim=self.s.sim_time,
            data=data,
        )
        self.notes.append(n)
        self._log("system", "notification", {"to": to, "kind": kind, "incident": n.incident_id, "text": text.get("en")})
        self._publish("notify", note=n.model_dump())

    def _get(self, incident_id: str) -> Incident:
        inc = self.incidents.get(incident_id)
        if inc is None:
            raise ApiError(404, "unknown_incident", f"no incident {incident_id}")
        return inc

    def _vehicle_of(self, driver: str):
        return next((v for v in self.s.scenario.vehicles if (v.driver or "").casefold() == driver.casefold()), None)

    def _reserved(self, except_incident: str | None = None) -> set[str]:
        """Vehicles tied up by another rescue that is offering or has been accepted."""
        out: set[str] = set()
        for i in self.incidents.values():
            if i.id != except_incident and i.state in OFFERING and 0 <= i.current < len(i.shortlist):
                out.add(i.shortlist[i.current])
        return out

    # --- 1. report and read-back --------------------------------------------------------------
    def report(
        self,
        driver: str,
        transcript: str,
        language: str | None = None,
        location_id: str | None = None,
        breakdown: bool | None = None,
        source: str = "text",
        engine: str | None = None,
    ) -> Incident:
        sc = self.s.scenario
        veh = self._vehicle_of(driver)
        if veh is None:
            raise ApiError(404, "unknown_driver", f"no driver named {driver!r}")
        if veh.status == "failed":
            raise ApiError(409, "already_failed", f"{veh.id} is already registered as broken down")
        if self.s.plan is None:
            raise ApiError(409, "no_plan", "there is no plan yet")
        if any(i.vehicle_id == veh.id and i.state not in TERMINAL for i in self.incidents.values()):
            raise ApiError(409, "incident_open", f"{veh.id} already has an open report")
        if location_id and location_id not in {loc.id for loc in sc.locations}:
            raise ApiError(422, "unknown_location", f"{location_id!r} is not a known place")

        lang = language if language in LANGS else veh.language
        ex = extract(transcript, sc)
        loc = location_id or ex.location_id
        is_breakdown = breakdown if breakdown is not None else ex.breakdown
        self._n_inc += 1
        inc = Incident(
            id=f"INC-{self._n_inc}",
            driver=veh.driver or driver,
            vehicle_id=veh.id,
            language=lang,
            transcript=transcript,
            source=source,
            state="REPORTED",
        )  # type: ignore[arg-type]
        self.incidents[inc.id] = inc
        inc.history.append(HistoryItem(wall=self.wall(), sim=self.s.sim_time, state="REPORTED"))
        self._log(
            inc.driver,
            "incident_reported",
            {
                "incident": inc.id,
                "vehicle": veh.id,
                "transcript": transcript,
                "source": source,
                "language": lang,
                "engine": engine,
            },
        )

        if loc is None:
            names = [self._loc(i) for i in ex.location_ids]
            why = (
                f"Your report mentions more than one place ({', '.join(names)}). Choose where the vehicle is."
                if names
                else "I could not find a place I know in your report. Choose where the vehicle is."
            )
            inc.known_locations = [{"id": loc_.id, "name": loc_.name} for loc_ in sc.locations]
            return self._reject(inc, why)
        if not is_breakdown:
            inc.location_id, inc.location_name = loc, self._loc(loc)
            return self._reject(
                inc, "I could not tell that the vehicle broke down. If it did, choose Vehicle broke down to report it."
            )
        self._fill_readback(inc, loc)
        inc.confirm_deadline = self.wall() + self.cfg.driver_confirm
        self._publish("incident", id=inc.id, state=inc.state)
        self.notify(f"driver:{inc.driver}", "readback", inc.readback, inc, incident=inc.id)
        return inc

    def _reject(self, inc: Incident, why: str) -> Incident:
        self._set(inc, "REJECTED", why)
        self._log(inc.driver, "report_rejected", {"incident": inc.id, "reason": why, "transcript": inc.transcript})
        return inc

    def _fill_readback(self, inc: Incident, loc_id: str) -> None:
        sc = self.s.scenario
        inc.location_id, inc.location_name = loc_id, self._loc(loc_id)
        now = self.s.incident_time()
        inc.parcels = remaining_parcels(self.s.plan, inc.vehicle_id, now)  # type: ignore[arg-type]
        inc.primary = pick_primary(sc, inc.parcels)
        if inc.primary:
            d = sc.delivery(inc.primary)
            inc.readback = say_all("readback", place=self._place(loc_id), parcel=d.id, due=hhmm(d.window_end))
        else:
            inc.readback = say_all("readback_empty", place=self._place(loc_id))

    def confirm(self, incident_id: str, confirmed: bool, location_id: str | None = None) -> Incident:
        inc = self._get(incident_id)
        if inc.state != "REPORTED":
            raise ApiError(409, "wrong_state", f"{inc.id} is {inc.state}, not waiting for confirmation")
        if location_id:  # the driver corrected the place
            if location_id not in {loc.id for loc in self.s.scenario.locations}:
                raise ApiError(422, "unknown_location", f"{location_id!r} is not a known place")
            self._fill_readback(inc, location_id)
            inc.confirm_deadline = self.wall() + self.cfg.driver_confirm
            self._log(inc.driver, "readback_edited", {"incident": inc.id, "location": location_id})
            self.notify(f"driver:{inc.driver}", "readback", inc.readback, inc, incident=inc.id)
            return inc
        if not confirmed:
            self._set(inc, "CANCELLED", "the driver said the read-back was wrong")
            inc.result = "The driver rejected the read-back. They can report again."
            return inc
        self._log(inc.driver, "readback_confirmed", {"incident": inc.id})
        self._set(inc, "DRIVER_CONFIRMED")
        inc.confirm_deadline = None
        self._propose(inc)
        if inc.proposal is None or inc.primary is None:  # nothing aboard to rescue
            self._register_failure_only(inc)
            return inc
        self._await_head(inc)
        return inc

    # --- 2. proposal and head approval --------------------------------------------------------
    def _propose(self, inc: Incident) -> None:
        now = self.s.incident_time()
        inc.failure_time = inc.failure_time if inc.failure_time is not None else now
        inc.parcels = remaining_parcels(self.s.plan, inc.vehicle_id, now)  # type: ignore[arg-type]
        inc.primary = pick_primary(self.s.scenario, inc.parcels)
        if inc.primary is None:
            inc.proposal = None
            return
        inc.proposal = rank(
            self.s.scenario,
            self.s.plan,
            inc.vehicle_id,
            inc.location_id or "",
            now,  # type: ignore[arg-type]
            self.s.version,
            self._reserved(inc.id),
        )

    def _await_head(self, inc: Incident, reason: str = "") -> None:
        inc.head_deadline = self.wall() + self.cfg.head_response
        inc.approver_role = "head"
        self._set(inc, "AWAITING_HEAD", reason)
        p = inc.proposal
        assert p is not None
        self.notify(f"driver:{inc.driver}", "awaiting", say_all("awaiting"), inc, incident=inc.id)
        self._notify_head(inc, "head")
        self.notify(
            "role:dispatcher",
            "incident",
            {
                "en": f"{inc.vehicle_id} ({inc.driver}) broke down at "
                f"{inc.location_name}. Waiting for the head's decision."
            },
            inc,
        )

    def _notify_head(self, inc: Incident, role: str) -> None:
        p = inc.proposal
        assert p is not None
        ok = p.feasible
        due = hhmm(p.primary_due) if p.primary_due is not None else ""
        if ok:
            lead = ok[0]
            text = (
                f"{inc.vehicle_id} ({inc.driver}) broke down at {inc.location_name} carrying urgent {p.primary} "
                f"due {due}. Recommended: {lead.driver} ({lead.vehicle_id}). {len(ok) - 1} backup"
                f"{'' if len(ok) == 2 else 's'}. Review now."
            )
        else:
            text = (
                f"{inc.vehicle_id} ({inc.driver}) broke down at {inc.location_name} carrying {p.primary} due {due}. "
                "No driver can rescue it in time. Review now."
            )
        self.notify(f"role:{role}", "head_alert", {"en": text}, inc, incident=inc.id)

    def approve(
        self, incident_id: str, by: str, shortlist: list[str], proposal_version: int, role: str = "head"
    ) -> Incident:
        inc = self._get(incident_id)
        if inc.state != "AWAITING_HEAD" or inc.proposal is None:
            raise ApiError(409, "wrong_state", f"{inc.id} is {inc.state}, not waiting for approval")
        p = inc.proposal
        if proposal_version != p.plan_version or p.plan_version != self.s.version:
            self._log(
                by, "approval_refused", {"incident": inc.id, "reason": "the plan changed; review the new proposal"}
            )
            raise ApiError(409, "stale_proposal", "The plan changed since this proposal. Review the new one.")
        ok = {c.vehicle_id for c in p.feasible}
        if not ok:
            if shortlist:
                raise ApiError(
                    422, "bad_shortlist", "No driver can rescue this in time, so there is nobody to approve."
                )
        else:
            if not shortlist or len(shortlist) > self.cfg.max_shortlist:
                raise ApiError(422, "bad_shortlist", f"Approve between 1 and {self.cfg.max_shortlist} drivers.")
            if len(set(shortlist)) != len(shortlist) or any(v not in ok for v in shortlist):
                raise ApiError(422, "bad_shortlist", "Every approved driver must be on the feasible list, once.")
        inc.approved_by, inc.approved_version, inc.shortlist = by, self.s.version, list(shortlist)
        inc.approver_role = "backup" if role == "backup" else "head"
        inc.head_deadline = None
        self._log(
            by,
            "head_approved",
            {"incident": inc.id, "role": role, "shortlist": shortlist, "plan_version": self.s.version},
        )
        self._set(inc, "HEAD_APPROVED", f"approved by {by}: {', '.join(shortlist) or 'nobody can rescue'}")
        if not shortlist:
            self._exhausted(inc, "no driver can rescue it in time")
        else:
            self._start_offer(inc, 0)
        return inc

    def reject(self, incident_id: str, by: str) -> Incident:
        inc = self._get(incident_id)
        if inc.state != "AWAITING_HEAD":
            raise ApiError(409, "wrong_state", f"{inc.id} is {inc.state}, not waiting for approval")
        self._log(by, "head_rejected", {"incident": inc.id})
        self._set(inc, "CANCELLED", f"rejected by {by}")
        inc.result = f"Rejected by {by}. The breakdown is not registered; handle it from the dispatch screen."
        self.notify(f"driver:{inc.driver}", "cancelled", say_all("cancelled"), inc)
        self.notify("role:dispatcher", "incident", {"en": f"The head rejected the rescue for {inc.vehicle_id}."}, inc)
        return inc

    # --- 3. offers -------------------------------------------------------------------------------
    def _facts(self, inc: Incident) -> dict[str, Any]:
        d = self.s.scenario.delivery(inc.primary or "")
        return {
            "parcel": d.id,
            "site": self._place(inc.location_id),
            "dest": self._place(d.location),
            "due": hhmm(d.window_end),
        }

    def _start_offer(self, inc: Incident, start: int) -> None:
        """Offer to the first approved driver, from index `start`, who is still free and still able."""
        assert inc.proposal is not None and inc.primary is not None
        now_sim = self.s.incident_time()
        failure = VehicleFailure(
            vehicle_id=inc.vehicle_id, time=inc.failure_time or now_sim, location=inc.location_id or ""
        )
        for idx in range(start, len(inc.shortlist)):
            vid = inc.shortlist[idx]
            if vid in self._reserved(inc.id):
                self._log(
                    "system",
                    "candidate_skipped",
                    {"incident": inc.id, "vehicle": vid, "reason": "busy with another rescue"},
                )
                continue
            cand, _ = evaluate(self.s.scenario, self.s.plan, failure, inc.primary, vid, now_sim)  # type: ignore[arg-type]
            if not cand.feasible:
                self._log("system", "candidate_skipped", {"incident": inc.id, "vehicle": vid, "reason": cand.reason})
                self._set(inc, "CANDIDATE_DECLINED", f"{vid} is no longer able: {cand.reason}")
                continue
            veh = self.s.scenario.vehicle(vid)
            self._n_off += 1
            facts = self._facts(inc)
            off = Offer(
                id=f"O-{self._n_off}",
                incident_id=inc.id,
                index=idx,
                vehicle_id=vid,
                driver=veh.driver,
                channel="push",
                sent=self.wall(),
                deadline=self.wall() + self.cfg.push_timeout,
                text=say_all("offer", **facts),
                script=say_all("call_script", **facts),
                language=veh.language,
            )
            self.offers[off.id] = off
            inc.current = idx
            self._set(inc, "OFFER_PUSHED", f"offered to {veh.driver} ({vid})")
            self._log(
                "system",
                "offer_pushed",
                {
                    "incident": inc.id,
                    "offer": off.id,
                    "vehicle": vid,
                    "driver": veh.driver,
                    "deadline_s": self.cfg.push_timeout,
                },
            )
            self.notify(f"driver:{veh.driver}", "offer", off.text, inc, offer=off.id, deadline=off.deadline)
            self.notify(
                "role:dispatcher", "incident", {"en": f"Offer sent to {veh.driver} ({vid}). 60 s to answer."}, inc
            )
            return
        self._exhausted(inc, "no approved driver accepted")

    def _offers_of(self, inc: Incident) -> list[Offer]:
        return [o for o in self.offers.values() if o.incident_id == inc.id]

    def _close_open(self, inc: Incident, outcome: str, status: str = "closed", except_id: str | None = None) -> None:
        for o in self._offers_of(inc):
            if o.status == "open" and o.id != except_id:
                o.status, o.outcome, o.closed = status, outcome, self.wall()  # type: ignore[assignment]
                self._log(
                    "system",
                    "offer_closed",
                    {"incident": inc.id, "offer": o.id, "channel": o.channel, "outcome": outcome},
                )

    def respond(self, offer_id: str, response: str, via: str = "tap", by: str | None = None) -> Incident:
        off = self.offers.get(offer_id)
        if off is None:
            raise ApiError(404, "unknown_offer", f"no offer {offer_id}")
        inc = self._get(off.incident_id)
        who = by or off.driver or "driver"
        if off.status != "open" or inc.state not in ("OFFER_PUSHED", "CALL_ESCALATED"):
            self._log(
                who,
                "late_response_refused",
                {
                    "incident": inc.id,
                    "offer": off.id,
                    "response": response,
                    "via": via,
                    "offer_status": off.status,
                    "incident_state": inc.state,
                },
            )
            raise ApiError(409, "offer_closed", "This offer is closed. Nothing was changed.")
        if via == "tap" and off.channel != "push":
            raise ApiError(422, "wrong_channel", "A call is answered on the call, not in the app.")
        if response == "decline":
            self._log(who, "offer_declined", {"incident": inc.id, "offer": off.id, "via": via})
            self._declined(inc, off, f"declined by {off.driver} ({via})", "declined")
        elif response == "accept":
            self._accept(inc, off, via, who)
        else:
            raise ApiError(422, "bad_response", "Respond with accept or decline.")
        return inc

    def skip_wait(self, offer_id: str) -> Incident:
        """A presenter's shortcut: treat an unanswered app offer as if its time had already run out."""
        off = self.offers.get(offer_id)
        if off is None:
            raise ApiError(404, "unknown_offer", f"no offer {offer_id}")
        inc = self._get(off.incident_id)
        if off.channel != "push" or off.status != "open":
            raise ApiError(409, "offer_closed", "This offer is closed. Nothing was changed.")
        self._log("presenter", "offer_wait_skipped", {"incident": inc.id, "offer": off.id})
        off.deadline = self.wall()
        self.tick()
        return inc

    def telephony_event(self, offer_id: str, outcome: str, how: str | None = None) -> Incident:
        """What a phone call reports back. The real provider (or the simulate buttons) calls this."""
        off = self.offers.get(offer_id)
        if off is None:
            raise ApiError(404, "unknown_offer", f"no offer {offer_id}")
        inc = self._get(off.incident_id)
        who = off.driver or "driver"
        if off.channel != "call" or off.status != "open" or inc.state != "CALL_ESCALATED":
            self._log(
                who,
                "late_response_refused",
                {
                    "incident": inc.id,
                    "offer": off.id,
                    "outcome": outcome,
                    "via": "call",
                    "offer_status": off.status,
                    "incident_state": inc.state,
                },
            )
            raise ApiError(409, "offer_closed", "This call is already finished. Nothing was changed.")
        self._log("telephony", "call_event", {"incident": inc.id, "offer": off.id, "outcome": outcome, "how": how})
        if outcome == "answered":
            off.call_state = "in_call"
            line = self.calls is not None and self.calls.ready()
            talk = self.cfg.conversation_limit if line else self.cfg.browser_conversation_limit
            off.conversation_deadline = self.wall() + talk
            self._publish("incident", id=inc.id, state=inc.state)
        elif outcome == "confirmed":
            self._accept(inc, off, "call", who, how)
        elif outcome == "declined":
            self._declined(inc, off, f"{off.driver} said no on the call", "declined")
        elif outcome == "unclear":  # the agent already asked twice
            self._declined(inc, off, f"{off.driver}'s answer on the call was unclear", "timed_out")
        elif outcome in ("no_answer", "voicemail", "busy"):
            self._declined(inc, off, f"the call to {off.driver} was not answered ({outcome})", "timed_out")
        elif outcome == "ambiguous":
            off.ambiguous += 1  # the agent repeats once; a second unclear answer counts as no response
            if off.ambiguous >= 2:
                self._declined(inc, off, f"{off.driver}'s answer on the call was unclear", "timed_out")
            else:
                self._publish("incident", id=inc.id, state=inc.state)
        else:
            raise ApiError(422, "bad_outcome", f"unknown call outcome {outcome!r}")
        return inc

    # --- 4. acceptance, re-validation, commit ----------------------------------------------------
    def _accept(self, inc: Incident, off: Offer, via: str, who: str, how: str | None = None) -> None:
        inc.claim = {
            "offer": off.id,
            "vehicle": off.vehicle_id,
            "via": via,
            "how": how,
            "at": self.wall(),
        }  # the single claim
        off.status, off.outcome, off.closed = "accepted", f"accepted by {via}", self.wall()
        self._close_open(inc, "another response won", except_id=off.id)
        self._log(who, "offer_accepted", {"incident": inc.id, "offer": off.id, "via": via, "how": how})
        self._set(inc, "ACCEPTED", f"{off.driver} ({off.vehicle_id}) accepted by {via}{f' ({how})' if how else ''}")
        try:
            self._commit_rescue(inc, off, via)
        except ApiError as e:
            self._log(
                "system", "revalidation_failed", {"incident": inc.id, "vehicle": off.vehicle_id, "reason": e.message}
            )
            inc.claim = None
            self._declined(inc, None, f"{off.driver} accepted but it is no longer feasible: {e.message}", None)

    def _failure(self, inc: Incident) -> VehicleFailure:
        return VehicleFailure(
            vehicle_id=inc.vehicle_id, time=inc.failure_time or self.s.incident_time(), location=inc.location_id or ""
        )

    def _commit_rescue(self, inc: Incident, off: Offer, via: str) -> None:
        assert inc.primary is not None
        now = self.s.incident_time()
        prev = self.s.compute(self._failure(inc), "system", assign={inc.primary: off.vehicle_id}, now=now)
        placed = {s.delivery_id for s in prev.result.plan.route(off.vehicle_id).stops if s.kind == "delivery"}
        if inc.primary not in placed:
            why = next(
                (u.reason for u in prev.result.plan.unplaced if u.delivery_id == inc.primary),
                "it cannot be delivered in time",
            )
            raise ApiError(409, "not_feasible", why)
        self._committing.add(inc.id)
        try:
            self.s.commit(
                prev,
                inc.approved_by or "head",
                inc.approved_by,
                meta={"rescue": inc.id, "rescuer": off.vehicle_id, "via": via},
            )
        finally:
            self._committing.discard(inc.id)
        route = prev.result.plan.route(off.vehicle_id)
        site = [s for s in route.stops if s.kind == "pickup" and s.location == inc.location_id]
        eta = min((s.arrival for s in site), default=None)
        drop = next(s for s in route.stops if s.kind == "delivery" and s.delivery_id == inc.primary)
        self._set(
            inc,
            "COMMITTED",
            f"{off.driver} ({off.vehicle_id}) will deliver {inc.primary} at {hhmm(drop.service_start)}",
        )
        inc.result = (
            f"{off.driver} ({off.vehicle_id}) reaches {inc.location_name} at {hhmm(eta)} and delivers "
            f"{inc.primary} at {hhmm(drop.service_start)}."
        )
        # only now is anyone told help is coming
        self.notify(
            f"driver:{inc.driver}",
            "on_the_way",
            say_all(
                "on_the_way",
                driver=off.driver or off.vehicle_id,
                vehicle=off.vehicle_id,
                eta=hhmm(eta),
                parcel=inc.primary,
            ),
            inc,
            eta=eta,
            rescuer=off.vehicle_id,
        )
        self.notify(f"driver:{off.driver}", "confirmed", say_all("accepted_thanks", **self._facts(inc)), inc)
        self.notify("role:head", "committed", {"en": inc.result}, inc)
        self.notify(
            "role:dispatcher",
            "committed",
            {"en": f"Rescue committed. {inc.result} Review the changes and customer messages."},
            inc,
        )

    def _declined(self, inc: Incident, off: Offer | None, why: str, status: str | None = "declined") -> None:
        if off is not None and status:
            off.status, off.outcome, off.closed = status, why, self.wall()  # type: ignore[assignment]
        self._close_open(inc, why)
        self._set(inc, "CANDIDATE_DECLINED", why)
        if off is not None:
            self.notify(f"driver:{off.driver}", "stood_down", say_all("stood_down"), inc)
        self._start_offer(inc, inc.current + 1)

    def _exhausted(self, inc: Incident, why: str) -> None:
        """Nobody took it. The failure is still registered, but the main parcel is reported undeliverable."""
        assert inc.primary is not None
        reason = "no rescue driver accepted it in time"
        try:
            prev = self.s.compute(
                self._failure(inc), "system", forbidden={inc.primary: reason}, now=self.s.incident_time()
            )
            self._committing.add(inc.id)
            try:
                self.s.commit(prev, "system", inc.approved_by, meta={"rescue": inc.id, "exhausted": True})
            finally:
                self._committing.discard(inc.id)
        except ApiError as e:
            self._log("system", "exhausted_without_plan_change", {"incident": inc.id, "reason": e.message})
        self._set(inc, "EXHAUSTED", why)
        inc.result = f"Nobody could rescue {inc.primary}. It is marked undeliverable; the customer needs to be told."
        self.notify(f"driver:{inc.driver}", "no_rescue", say_all("no_rescue"), inc)
        self.notify("role:head", "exhausted", {"en": inc.result}, inc)
        self.notify("role:dispatcher", "exhausted", {"en": inc.result}, inc)

    def _register_failure_only(self, inc: Incident) -> None:
        """Nothing is left on the vehicle, so there is no rescue to arrange: just register the breakdown."""
        prev = self.s.compute(self._failure(inc), "system", now=self.s.incident_time())
        self._committing.add(inc.id)
        try:
            self.s.commit(prev, inc.driver, inc.driver, meta={"rescue": inc.id, "nothing_aboard": True})
        finally:
            self._committing.discard(inc.id)
        self._set(inc, "COMMITTED", "nothing aboard; breakdown registered")
        inc.result = "The breakdown is registered. No parcels were left on the vehicle."
        self.notify(f"driver:{inc.driver}", "awaiting", say_all("awaiting"), inc)
        self.notify(
            "role:dispatcher",
            "committed",
            {"en": f"{inc.vehicle_id} ({inc.driver}) broke down at {inc.location_name}. Nothing was aboard."},
            inc,
        )

    # --- 5. plan changes void approvals -------------------------------------------------------
    def _plan_changed(self, reason: str) -> None:
        if reason in ("scenario_loaded", "plan_built"):  # a fresh start: nothing from before can still be open
            self.incidents.clear()
            self.offers.clear()
            self.notes.clear()
            self._committing.clear()
            return
        for inc in list(self.incidents.values()):
            if inc.state in TERMINAL or inc.id in self._committing:
                continue
            veh = self.s.scenario.vehicle(inc.vehicle_id)
            if veh.status == "failed":
                self._close_open(inc, "the breakdown was registered another way")
                self._set(inc, "CANCELLED", "the vehicle was registered as broken down from the dispatch screen")
                inc.result = "Handled from the dispatch screen."
                continue
            if inc.state == "AWAITING_HEAD":
                self._propose(inc)
                if inc.proposal is not None:
                    self._notify_head(inc, inc.approver_role)
                self._log("system", "proposal_refreshed", {"incident": inc.id, "reason": reason})
            elif inc.state in ("HEAD_APPROVED", "OFFER_PUSHED", "CALL_ESCALATED"):
                self._log("system", "approval_void", {"incident": inc.id, "reason": reason, "was": inc.state})
                for o in self._offers_of(inc):
                    if o.status == "open":
                        self.notify(f"driver:{o.driver}", "stood_down", say_all("stood_down"), inc)
                self._close_open(inc, "the plan changed, so the approval is void")
                inc.shortlist, inc.current, inc.claim, inc.approved_by, inc.approved_version = [], -1, None, None, None
                self._propose(inc)
                if inc.proposal is None:
                    self._register_failure_only(inc)
                    continue
                self._await_head(inc, "the plan changed, so the earlier approval is void")
            elif inc.state == "REPORTED":
                self._fill_readback(inc, inc.location_id or "")

    # --- 6. timers ---------------------------------------------------------------------------------
    def tick(self) -> None:
        now = self.wall()
        for inc in list(self.incidents.values()):
            if inc.state in TERMINAL:
                continue
            if inc.state == "REPORTED" and inc.confirm_deadline and now >= inc.confirm_deadline:
                inc.reprompts += 1
                if inc.reprompts >= self.cfg.max_reprompts:
                    self._set(inc, "CANCELLED", "the driver did not confirm the report")
                    inc.result = "The report was not confirmed, so it was dropped. The driver can report again."
                else:
                    inc.confirm_deadline = now + self.cfg.driver_confirm
                    self._log("system", "reprompt", {"incident": inc.id, "n": inc.reprompts})
                    self.notify(
                        f"driver:{inc.driver}",
                        "readback",
                        {k: f"{say('reprompt', k)} {v}" for k, v in inc.readback.items()},
                        inc,
                    )
            elif inc.state == "AWAITING_HEAD" and inc.head_deadline and now >= inc.head_deadline:
                self._head_timeout(inc, now)
            elif inc.state in ("OFFER_PUSHED", "CALL_ESCALATED"):
                self._tick_offers(inc, now)

    def _head_timeout(self, inc: Incident, now: float) -> None:
        self._set(inc, "HEAD_TIMEOUT", f"no answer from the {inc.approver_role}")
        self._log("system", "head_timeout", {"incident": inc.id, "role": inc.approver_role})
        if inc.approver_role == "head":
            inc.approver_role = "backup"
            inc.head_deadline = now + self.cfg.head_response
            self._set(inc, "AWAITING_HEAD", "escalated to the backup approver")
            self._notify_head(inc, "backup")
            self.notify(
                "role:dispatcher",
                "incident",
                {"en": f"The head did not respond for {inc.vehicle_id}. The backup approver has been asked."},
                inc,
            )
        else:
            inc.head_deadline = None
            inc.escalated_to_dispatcher = True
            self._set(inc, "AWAITING_HEAD", "nobody has responded; the dispatcher has been alerted")
            self.notify(
                "role:dispatcher",
                "incident",
                {"en": f"Nobody has approved the rescue for {inc.vehicle_id}. Decide now."},
                inc,
            )

    def _tick_offers(self, inc: Incident, now: float) -> None:
        for off in self._offers_of(inc):
            if off.status != "open":
                continue
            if off.channel == "push" and now >= off.deadline:
                off.status, off.outcome, off.closed = "timed_out", "no response in time", now
                self._log("system", "offer_timed_out", {"incident": inc.id, "offer": off.id})
                self._escalate_to_call(inc, off, now)
            elif off.channel == "call":
                if off.call_state == "ringing" and now >= off.deadline:
                    self._declined(inc, off, f"the call to {off.driver} rang with no answer", "timed_out")
                elif off.call_state == "in_call" and off.conversation_deadline and now >= off.conversation_deadline:
                    self._declined(inc, off, f"{off.driver} gave no clear answer on the call", "timed_out")

    def _ring_seconds(self) -> float:
        line = self.calls is not None and self.calls.ready()
        return self.cfg.ring_timeout if line else self.cfg.browser_ring_timeout

    def _escalate_to_call(self, inc: Incident, push: Offer, now: float) -> None:
        self._n_off += 1
        call = Offer(
            id=f"O-{self._n_off}",
            incident_id=inc.id,
            index=push.index,
            vehicle_id=push.vehicle_id,
            driver=push.driver,
            channel="call",
            sent=now,
            deadline=now + self._ring_seconds(),
            call_state="ringing",
            text=push.text,
            script=push.script,
            language=push.language,
        )
        self.offers[call.id] = call
        self._set(inc, "CALL_ESCALATED", f"calling {push.driver} ({push.vehicle_id})")
        self._log(
            "system",
            "call_placed",
            {"incident": inc.id, "offer": call.id, "driver": push.driver, "ring_s": self._ring_seconds()},
        )
        self.notify(
            f"driver:{push.driver}", "calling", {"en": "We are calling you now. Please answer."}, inc, offer=call.id
        )
        self.notify(
            "role:dispatcher",
            "incident",
            {"en": f"No answer in the app. Calling {push.driver} ({push.vehicle_id})."},
            inc,
        )
        self._start_real_call(inc, call)

    # --- the real phone call (when it is set up) -------------------------------------------------------
    def attach_calls(self, telephony: Any) -> None:
        self.calls = telephony

    def _start_real_call(self, inc: Incident, call: Offer) -> None:
        """Ring the driver's phone with the engine's own script. Without a phone line this does nothing and the
        dispatcher's simulate-the-call buttons stand in, through the very same events."""
        tel = self.calls
        if tel is None:
            return
        ctx = self._call_context(inc, call, tel)
        lang = ctx["language"]
        started = tel.start(
            call.id,
            call.driver,
            script=ctx["first_message"],
            language=lang,
            variables=ctx["variables"],
            ring_seconds=int(self._ring_seconds()),
            on_event=self._from_call,
            is_open=lambda: call.status == "open",
        )
        self._log(
            "system",
            "real_call_started" if started else "real_call_skipped",
            {"incident": inc.id, "offer": call.id, "driver": call.driver, "language": lang},
        )

    def _call_context(self, inc: Incident, call: Offer, tel: Any, language: str | None = None) -> dict[str, Any]:
        """What the call agent is told: the engine's own script, in the call language, and the facts it may repeat."""
        lang = language or tel.language_for(call.language)
        plain = {k: (v.get(lang, v["en"]) if isinstance(v, dict) else v) for k, v in self._facts(inc).items()}
        cand = next(
            (c for c in (inc.proposal.candidates if inc.proposal else []) if c.vehicle_id == call.vehicle_id), None
        )
        when = lambda t: hhmm(t) if t is not None else "not known"  # noqa: E731
        others = [p for p in inc.parcels if p != inc.primary]
        extra = {
            "driver": call.driver or "",
            "offer_id": call.id,
            "stranded_driver": inc.driver,
            "reach": when(cand.reach_site if cand else None),
            "leave": when(cand.leave_site if cand else None),
            "deliver": when(cand.delivery_time if cand else None),
            "other_parcels": ", ".join(others) or "none",
        }
        return {
            "first_message": call.script.get(lang) or call.script["en"],
            "language": lang,
            "variables": {**plain, **extra},
        }

    def _open_call(self, offer_id: str, driver: str | None) -> tuple[Incident, Offer]:
        off = self.offers.get(offer_id)
        if off is None:
            raise ApiError(404, "unknown_offer", f"no offer {offer_id}")
        inc = self._get(off.incident_id)
        if off.channel != "call" or off.status != "open" or inc.state != "CALL_ESCALATED":
            raise ApiError(409, "offer_closed", "This call is already finished. Nothing was changed.")
        if driver is not None and off.driver != driver:
            raise ApiError(403, "not_your_call", "This call is for another driver.")
        return inc, off

    def browser_call_context(self, offer_id: str, driver: str | None, language: str | None = None) -> dict[str, Any]:
        """The script and facts for a voice conversation held in the driver's own browser."""
        inc, off = self._open_call(offer_id, driver)
        assert self.calls is not None
        return self._call_context(inc, off, self.calls, language)

    def browser_call_started(self, offer_id: str, driver: str | None, conversation_id: str) -> None:
        """The driver's browser connected to the call agent: the call is answered, and we follow it to its outcome."""
        inc, off = self._open_call(offer_id, driver)
        assert self.calls is not None
        self._log("driver", "browser_call_started", {"incident": inc.id, "offer": off.id, "driver": off.driver})
        self.telephony_event(offer_id, "answered")
        self.calls.watch(
            offer_id,
            conversation_id,
            ring_seconds=int(self._ring_seconds()),
            on_event=self._from_call,
            is_open=lambda: off.status == "open",
        )

    def _from_call(self, offer_id: str, outcome: str, how: str | None = None) -> None:
        """An outcome from the phone line, arriving on the app's own thread."""
        try:
            self.telephony_event(offer_id, outcome, how)
        except ApiError:
            pass  # a late result: it was refused and logged already

    # --- views ---------------------------------------------------------------------------------------
    def incident_view(self, inc: Incident) -> dict[str, Any]:
        d = inc.model_dump()
        d["offers"] = [o.model_dump() for o in self._offers_of(inc)]
        d["active_offer"] = next((o.model_dump() for o in self._offers_of(inc) if o.status == "open"), None)
        return d

    def overview(self) -> dict[str, Any]:
        return {
            "server_time": self.wall(),
            "clock": {"sim": self.s.clock.now(), "speed": self.s.clock.speed},
            "config": self.cfg.__dict__,
            "incidents": [self.incident_view(i) for i in self.incidents.values()],
        }

    def speakable(self, what: str, ref: str, lang: str) -> str:
        """The exact sentence for something the system produced. Voice speaks only these."""
        text: str | None = None
        if what == "readback":
            text = self._get(ref).readback.get(lang)
        elif what == "offer":
            off = self.offers.get(ref)
            text = off.text.get(lang) if off else None
        elif what == "said":
            text = self.s.sayings.get(ref)
        elif what == "note":
            n = next((x for x in self.notes if str(x.id) == ref), None)
            text = n.text.get(lang) if n else None
        else:
            raise ApiError(422, "bad_kind", "Voice can speak a readback, an offer, a note or a recent answer.")
        if not text:
            raise ApiError(404, "nothing_to_say", "There is nothing to say for that.")
        return text

    def open_offers(self, driver: str) -> list[dict[str, Any]]:
        return [
            o.model_dump()
            for o in self.offers.values()
            if o.status == "open" and (o.driver or "").casefold() == driver.casefold()
        ]

    def notifications(self, to: str, after: int = 0) -> list[dict[str, Any]]:
        return [n.model_dump() for n in self.notes if n.to == to and n.id > after]


__all__ = ["Proposal", "RescueConfig", "RescueService"]
