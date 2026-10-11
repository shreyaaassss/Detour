"""The rescue flow, end to end through the API, with a fake wall clock so the 60-second timers are instant."""

import pytest
from fastapi.testclient import TestClient

from detour.api import create_app
from detour.engine.models import parse_hhmm as t
from detour.rescue.service import RescueConfig


class Wall:
    def __init__(self) -> None:
        self.t = 1_000_000.0

    def __call__(self) -> float:
        return self.t


class Rig:
    def __init__(self, tmp_path, **cfg) -> None:
        self.wall = Wall()
        self.app = create_app(
            tmp_path / "audit.jsonl",
            start_ticker=False,
            rescue_config=RescueConfig(**{"browser_ring_timeout": 25.0, **cfg}),
            wall=self.wall,
        )
        self.c = TestClient(self.app)
        self.svc = self.app.state.rescue

    def advance(self, seconds: float) -> None:
        self.wall.t += seconds
        self.svc.tick()

    def report(self, driver="Ravi", text="My truck broke down near Hadapsar and I can't make the 3 PM delivery.", **kw):
        r = self.c.post("/incidents/report", json={"driver": driver, "transcript": text, **kw})
        assert r.status_code == 200, r.text
        return r.json()["incident"]

    def confirm(self, iid, **kw):
        r = self.c.post(f"/incidents/{iid}/confirm", json=kw or {"confirmed": True})
        assert r.status_code == 200, r.text
        return r.json()["incident"]

    def inc(self, iid):
        return self.c.get(f"/incidents/{iid}").json()["incident"]

    def proposal(self, iid):
        return self.c.get(f"/incidents/{iid}/proposal").json()["proposal"]

    def approve(self, iid, shortlist=("V4", "V3", "V5"), by="head", role="head", version=None, expect=200):
        version = version if version is not None else self.proposal(iid)["plan_version"]
        r = self.c.post(
            f"/incidents/{iid}/approve",
            json={"approved_by": by, "shortlist": list(shortlist), "proposal_version": version, "role": role},
        )
        assert r.status_code == expect, r.text
        return r.json()

    def to_head(self, **kw):
        iid = self.report(**kw)["id"]
        self.confirm(iid)
        return iid

    def notes(self, to):
        return self.c.get("/notifications", params={"to": to}).json()["notifications"]

    def actions(self):
        return [e["action"] for e in self.c.get("/audit?limit=2000").json()["entries"]]

    def state(self):
        return self.c.get("/state").json()


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def test_the_worked_example(rig):
    before = rig.state()
    inc = rig.report()
    assert inc["state"] == "REPORTED" and inc["location_id"] == "hadapsar" and inc["primary"] == "D7"
    assert inc["readback"]["en"] == "Breakdown at Hadapsar, delivery D7 due 15:00. Correct?"
    assert "हडपसर" in inc["readback"]["mr"] and "D7" in inc["readback"]["hi"]
    iid = inc["id"]

    assert rig.confirm(iid)["state"] == "AWAITING_HEAD"
    p = rig.proposal(iid)
    ranked = [(c["vehicle_id"], c["rank"]) for c in p["candidates"] if c["feasible"]]
    assert ranked == [("V4", 1), ("V3", 2), ("V5", 3)]
    meera, sana, imran, arjun = p["candidates"]
    assert (meera["reach_site"], meera["leave_site"], meera["delivery_time"]) == (t("14:15"), t("14:20"), t("14:50"))
    assert (sana["reach_site"], sana["leave_site"], sana["delivery_time"]) == (t("14:20"), t("14:25"), t("14:55"))
    assert (imran["reach_site"], imran["leave_site"], imran["delivery_time"]) == (t("14:23"), t("14:28"), t("14:58"))
    assert arjun["vehicle_id"] == "V1" and not arjun["feasible"] and "15:07" in arjun["reason"]

    # nothing has changed in the plan, and the driver has only been told the request is waiting
    assert rig.state()["version"] == before["version"] and rig.state()["plan"] == before["plan"]
    kinds = [n["kind"] for n in rig.notes("driver:Ravi")]
    assert "awaiting" in kinds and "on_the_way" not in kinds
    assert "V4" in rig.notes("role:head")[-1]["text"]["en"] and "Meera" in rig.notes("role:head")[-1]["text"]["en"]

    rig.advance(95)  # the head reads it and approves
    out = rig.approve(iid)["incident"]
    assert out["state"] == "OFFER_PUSHED" and out["shortlist"] == ["V4", "V3", "V5"]
    offer = out["active_offer"]
    assert offer["driver"] == "Meera" and offer["channel"] == "push" and offer["deadline"] - offer["sent"] == 60
    assert "D7" in offer["text"]["en"] and "Hadapsar" in offer["text"]["en"] and "15:00" in offer["text"]["en"]
    assert rig.c.get("/offers", params={"driver": "Meera"}).json()["offers"][0]["id"] == offer["id"]

    rig.advance(60)  # Meera does not tap: after 60 s the call is placed
    out = rig.inc(iid)
    call = out["active_offer"]
    assert out["state"] == "CALL_ESCALATED" and call["channel"] == "call" and call["call_state"] == "ringing"
    assert [o["status"] for o in out["offers"]] == ["timed_out", "open"]
    assert "automated call" in call["script"]["en"] and "say confirm" in call["script"]["en"]

    assert rig.c.post("/telephony/webhook", json={"offer_id": call["id"], "outcome": "answered"}).status_code == 200
    assert rig.inc(iid)["active_offer"]["call_state"] == "in_call"
    done = rig.c.post("/telephony/webhook", json={"offer_id": call["id"], "outcome": "confirmed"}).json()["incident"]
    assert done["state"] == "COMMITTED" and done["claim"]["via"] == "call"

    # committed: the plan is updated and validated, and only now is Ravi told help is coming
    s = rig.state()
    assert s["version"] > before["version"] and s["report"]["valid"]
    assert [x["delivery_id"] for r in s["plan"]["routes"] if r["vehicle_id"] == "V2" for x in r["stops"]] == ["D1"]
    d7 = next(c for c in s["diff"]["changes"] if c["delivery_id"] == "D7")
    assert d7["status"] == "moved" and d7["new_vehicle"] == "V4" and d7["new_service"] == t("14:50")
    assert next(c for c in s["diff"]["changes"] if c["delivery_id"] == "D9")["status"] == "broken"
    way = [n for n in rig.notes("driver:Ravi") if n["kind"] == "on_the_way"]
    assert way and "14:15" in way[0]["text"]["en"] and "Meera" in way[0]["text"]["en"] and "D7" in way[0]["text"]["en"]
    assert "14:15" in way[0]["text"]["mr"]

    # everything is in the audit log
    acts = rig.actions()
    for a in (
        "incident_reported",
        "readback_confirmed",
        "head_approved",
        "offer_pushed",
        "offer_timed_out",
        "call_placed",
        "call_event",
        "offer_accepted",
        "disruption_applied",
        "notification",
    ):
        assert a in acts, a
    assert rig.c.get("/audit/verify").json()["valid"]

    msgs = rig.c.get("/messages").json()["messages"]
    assert {m["delivery_id"]: m["status"] for m in msgs} == {"D9": "broken", "D7": "moved", "D8": "moved"}
    assert all("V2" not in m["text"] and "Meera" not in m["text"] for m in msgs)  # nothing internal reaches a customer


def test_variant_a_first_candidate_does_not_answer(tmp_path):
    rig = Rig(tmp_path)
    iid = rig.to_head()
    rig.approve(iid)
    rig.advance(60)  # push times out -> call to Meera
    rig.advance(25)  # the call rings with no answer -> declined, Sana gets a fresh push
    out = rig.inc(iid)
    assert out["state"] == "OFFER_PUSHED" and out["active_offer"]["driver"] == "Sana" and out["current"] == 1
    sent = out["active_offer"]
    assert sent["deadline"] - sent["sent"] == 60
    assert "stood_down" in [n["kind"] for n in rig.notes("driver:Meera")]
    states = [h["state"] for h in out["history"]]
    assert states[-4:] == ["OFFER_PUSHED", "CALL_ESCALATED", "CANDIDATE_DECLINED", "OFFER_PUSHED"]


def test_variant_b_nobody_accepts(tmp_path):
    rig = Rig(tmp_path)
    iid = rig.to_head()
    rig.approve(iid)
    for _ in range(3):
        rig.advance(60)
        rig.advance(25)
    out = rig.inc(iid)
    assert out["state"] == "EXHAUSTED"
    s = rig.state()
    d7 = next(c for c in s["diff"]["changes"] if c["delivery_id"] == "D7")
    assert d7["status"] == "broken" and "no rescue driver accepted" in d7["reason"]
    assert s["report"]["valid"] and next(v for v in s["scenario"]["vehicles"] if v["id"] == "V2")["status"] == "failed"
    assert "no_rescue" in [n["kind"] for n in rig.notes("driver:Ravi")]
    assert "on_the_way" not in [n["kind"] for n in rig.notes("driver:Ravi")]
    assert "exhausted" in [n["kind"] for n in rig.notes("role:head")] and rig.notes("role:dispatcher")


def test_variant_c_head_is_silent(tmp_path):
    rig = Rig(tmp_path)
    iid = rig.to_head()
    rig.advance(119)
    assert rig.inc(iid)["approver_role"] == "head"
    rig.advance(2)
    out = rig.inc(iid)
    assert out["state"] == "AWAITING_HEAD" and out["approver_role"] == "backup"
    assert "head_timeout" in rig.actions()
    assert rig.notes("role:backup") and "Recommended" in rig.notes("role:backup")[0]["text"]["en"]
    assert rig.approve(iid, by="backup", role="backup")["incident"]["state"] == "OFFER_PUSHED"
    # a backup who is silent too alerts the dispatcher instead of cancelling
    iid2 = None
    rig2 = Rig(tmp_path / "x")
    iid2 = rig2.to_head()
    rig2.advance(121)
    rig2.advance(121)
    out = rig2.inc(iid2)
    assert out["state"] == "AWAITING_HEAD" and out["escalated_to_dispatcher"]


def test_one_claim_only_and_late_responses_are_refused(rig):
    iid = rig.to_head()
    rig.approve(iid)
    push = rig.inc(iid)["active_offer"]
    rig.advance(60)
    call = rig.inc(iid)["active_offer"]

    # a tap on the closed push is refused and logged
    r = rig.c.post(f"/offers/{push['id']}/respond", json={"response": "accept"})
    assert r.status_code == 409 and r.json()["code"] == "offer_closed"
    assert rig.inc(iid)["state"] == "CALL_ESCALATED"
    assert "late_response_refused" in rig.actions()

    rig.c.post("/telephony/webhook", json={"offer_id": call["id"], "outcome": "confirmed"})
    assert rig.inc(iid)["state"] == "COMMITTED"
    version = rig.state()["version"]
    # everything arriving after the winner is refused and changes nothing
    assert rig.c.post(f"/offers/{push['id']}/respond", json={"response": "accept"}).status_code == 409
    assert rig.c.post(f"/offers/{call['id']}/respond", json={"response": "accept", "via": "call"}).status_code == 409
    assert rig.c.post("/telephony/webhook", json={"offer_id": call["id"], "outcome": "declined"}).status_code == 409
    assert rig.state()["version"] == version and rig.inc(iid)["claim"]["via"] == "call"
    assert rig.actions().count("late_response_refused") >= 4


def test_tap_accepts_and_a_second_tap_cannot(rig):
    iid = rig.to_head()
    rig.approve(iid)
    off = rig.inc(iid)["active_offer"]
    first = rig.c.post(f"/offers/{off['id']}/respond", json={"response": "accept"})
    assert first.status_code == 200 and first.json()["incident"]["state"] == "COMMITTED"
    assert rig.c.post(f"/offers/{off['id']}/respond", json={"response": "accept"}).status_code == 409
    assert [a for a in rig.actions() if a == "disruption_applied"] == ["disruption_applied"]


def test_decline_moves_to_the_next_driver(rig):
    iid = rig.to_head()
    rig.approve(iid)
    off = rig.inc(iid)["active_offer"]
    out = rig.c.post(f"/offers/{off['id']}/respond", json={"response": "decline"}).json()["incident"]
    assert out["state"] == "OFFER_PUSHED" and out["active_offer"]["driver"] == "Sana"


def test_call_outcomes(rig):
    iid = rig.to_head()
    rig.approve(iid)
    rig.advance(60)
    call = rig.inc(iid)["active_offer"]
    # unclear once: the agent repeats; unclear twice: no response
    rig.c.post("/telephony/webhook", json={"offer_id": call["id"], "outcome": "ambiguous"})
    assert rig.inc(iid)["state"] == "CALL_ESCALATED"
    rig.c.post("/telephony/webhook", json={"offer_id": call["id"], "outcome": "ambiguous"})
    assert rig.inc(iid)["active_offer"]["driver"] == "Sana"
    # voicemail counts as declined
    rig.advance(60)
    call2 = rig.inc(iid)["active_offer"]
    rig.c.post("/telephony/webhook", json={"offer_id": call2["id"], "outcome": "voicemail"})
    assert rig.inc(iid)["active_offer"]["driver"] == "Imran"
    # a call that is answered but never resolved is cut off after the conversation limit
    rig.advance(60)
    call3 = rig.inc(iid)["active_offer"]
    rig.c.post("/telephony/webhook", json={"offer_id": call3["id"], "outcome": "answered"})
    rig.advance(44)
    assert rig.inc(iid)["state"] == "CALL_ESCALATED"
    rig.advance(2)
    assert rig.inc(iid)["state"] == "EXHAUSTED"


def test_accepting_is_revalidated_when_time_has_passed(rig):
    iid = rig.to_head()
    rig.approve(iid, shortlist=["V5", "V4"])
    imran = rig.inc(iid)["active_offer"]
    assert imran["driver"] == "Imran"
    # ten simulated minutes pass: Imran can no longer make the 15:00 window
    rig.c.post("/clock", json={"sim_time": "14:10"})
    out = rig.c.post(f"/offers/{imran['id']}/respond", json={"response": "accept"}).json()["incident"]
    assert out["state"] == "OFFER_PUSHED" and out["active_offer"]["driver"] == "Meera"
    assert out["claim"] is None
    assert "revalidation_failed" in rig.actions()
    assert rig.state()["plan"]["routes"][1]["stops"][-1]["delivery_id"] == "D9"  # the plan was not touched


def test_a_plan_change_voids_the_approval(rig):
    iid = rig.to_head()
    old_version = rig.proposal(iid)["plan_version"]
    rig.approve(iid)
    off = rig.inc(iid)["active_offer"]
    closure = {
        "type": "road_closure",
        "a": "camp",
        "b": "kharadi",
        "start": t("14:00"),
        "end": t("16:00"),
        "added_minutes": 20,
        "reported_at": t("14:00"),
    }
    assert rig.c.post("/disruptions", json={"disruption": closure}).status_code == 200

    out = rig.inc(iid)
    assert out["state"] == "AWAITING_HEAD" and out["shortlist"] == [] and out["approved_by"] is None
    assert [o["status"] for o in out["offers"]] == ["closed"]
    assert rig.proposal(iid)["plan_version"] > old_version
    assert "approval_void" in rig.actions() and "stood_down" in [n["kind"] for n in rig.notes("driver:Meera")]
    # the old offer cannot be answered and the old proposal cannot be approved
    assert rig.c.post(f"/offers/{off['id']}/respond", json={"response": "accept"}).status_code == 409
    rig.approve(iid, version=old_version, expect=409)
    assert rig.approve(iid)["incident"]["state"] == "OFFER_PUSHED"  # a fresh approval works


def test_plan_change_while_waiting_refreshes_the_proposal(rig):
    iid = rig.to_head()
    v = rig.proposal(iid)["plan_version"]
    urgent = {
        "type": "urgent_delivery",
        "id": "D40",
        "location": "camp",
        "size": 5,
        "window_start": t("14:10"),
        "window_end": t("17:00"),
        "time": t("14:05"),
    }
    rig.c.post("/disruptions", json={"disruption": urgent})
    assert rig.proposal(iid)["plan_version"] > v and rig.inc(iid)["state"] == "AWAITING_HEAD"
    assert "proposal_refreshed" in rig.actions()


def test_approval_rules(rig):
    iid = rig.to_head()
    for bad in ([], ["V1"], ["V4", "V4"], ["V4", "V3", "V5", "V1"], ["V9"]):
        r = rig.c.post(
            f"/incidents/{iid}/approve",
            json={"approved_by": "head", "shortlist": bad, "proposal_version": rig.proposal(iid)["plan_version"]},
        )
        assert r.status_code == 422, bad
    assert rig.inc(iid)["state"] == "AWAITING_HEAD"
    assert (
        rig.approve(iid, shortlist=["V3"])["incident"]["active_offer"]["driver"] == "Sana"
    )  # head may pick any feasible driver
    assert (
        rig.c.post(
            f"/incidents/{iid}/approve", json={"approved_by": "head", "shortlist": ["V4"], "proposal_version": 1}
        ).status_code
        == 409
    )  # wrong state


def test_head_can_reject(rig):
    iid = rig.to_head()
    r = rig.c.post(f"/incidents/{iid}/reject", json={"by": "head"}).json()["incident"]
    assert r["state"] == "CANCELLED"
    assert "cancelled" in [n["kind"] for n in rig.notes("driver:Ravi")]
    assert next(v for v in rig.state()["scenario"]["vehicles"] if v["id"] == "V2")["status"] == "active"


def test_unknown_location_is_rejected_not_guessed(rig):
    inc = rig.report(text="My truck broke down near Atlantis")
    assert inc["state"] == "REJECTED" and "could not find a place" in inc["note"]
    assert {"id": "hadapsar", "name": "Hadapsar"} in inc["known_locations"]
    both = rig.report(text="Truck broke down near Hadapsar, delivering to Aundh")
    assert both["state"] == "REJECTED" and "more than one place" in both["note"]
    assert "report_rejected" in rig.actions()
    assert rig.state()["plan"] == rig.state()["original"]  # nothing happened to the plan


def test_a_report_that_is_not_a_breakdown_is_not_assumed_to_be_one(rig):
    inc = rig.report(text="I will be late near Hadapsar")
    assert inc["state"] == "REJECTED" and "could not tell" in inc["note"]
    # the button flow supplies both facts explicitly
    ok = rig.report(text="", location_id="hadapsar", breakdown=True, source="buttons")
    assert ok["state"] == "REPORTED" and ok["source"] == "buttons"


@pytest.mark.parametrize(
    "text",
    ["माझी गाडी हडपसर जवळ बिघडली", "मेरी गाड़ी हडपसर के पास खराब हो गई", "Truck broke down at hadapsar!"],
)
def test_reports_in_marathi_hindi_and_english(tmp_path, text):
    rig = Rig(tmp_path)
    inc = rig.report(text=text)
    assert inc["state"] == "REPORTED" and inc["location_id"] == "hadapsar"


def test_driver_can_edit_or_reject_the_readback(rig):
    iid = rig.report(text="broke down near Hadapsar")["id"]
    out = rig.confirm(iid, location_id="camp")
    assert out["state"] == "REPORTED" and out["location_id"] == "camp" and "Camp" in out["readback"]["en"]
    assert rig.c.post(f"/incidents/{iid}/confirm", json={"location_id": "nowhere"}).status_code == 422
    assert rig.confirm(iid, confirmed=False)["state"] == "CANCELLED"
    assert rig.state()["plan"] == rig.state()["original"]


def test_unconfirmed_reports_are_reprompted_then_dropped(rig):
    iid = rig.report()["id"]
    rig.advance(31)
    assert rig.inc(iid)["reprompts"] == 1 and len([n for n in rig.notes("driver:Ravi") if n["kind"] == "readback"]) == 2
    rig.advance(31)
    rig.advance(31)
    assert rig.inc(iid)["state"] == "CANCELLED"


def test_report_guards(rig):
    assert (
        rig.c.post("/incidents/report", json={"driver": "Nobody", "transcript": "broke down at Hadapsar"}).status_code
        == 404
    )
    rig.report()
    assert (
        rig.c.post("/incidents/report", json={"driver": "ravi", "transcript": "broke down at Hadapsar"}).status_code
        == 409
    )
    rig.c.post("/reset")
    assert rig.c.get("/incidents").json()["incidents"] == []  # a reload clears everything open


def test_nothing_aboard_just_registers_the_breakdown(rig):
    rig.c.post("/clock", json={"sim_time": "17:30"})
    iid = rig.report(driver="Arjun", text="broke down at Camp")["id"]
    out = rig.confirm(iid)
    assert out["state"] == "COMMITTED" and "No parcels" in out["result"]
    assert next(v for v in rig.state()["scenario"]["vehicles"] if v["id"] == "V1")["status"] == "failed"


def test_two_breakdowns_never_share_a_rescuer(tmp_path):
    rig = Rig(tmp_path)
    first = rig.to_head()
    rig.approve(first, shortlist=["V4"])  # Meera is being offered the first rescue
    second = rig.report(driver="Imran", text="broke down near Camp")["id"]
    rig.confirm(second)
    p = rig.proposal(second)
    meera = next(c for c in p["candidates"] if c["vehicle_id"] == "V4")
    assert not meera["feasible"] and "busy with another rescue" in meera["reason"]
    # approving a list that includes her is refused
    r = rig.c.post(
        f"/incidents/{second}/approve",
        json={"approved_by": "head", "shortlist": ["V4"], "proposal_version": p["plan_version"]},
    )
    assert r.status_code == 422


def test_clock_api(rig):
    assert rig.c.get("/clock").json() == {**rig.c.get("/clock").json(), "sim": t("14:05"), "speed": 0}
    r = rig.c.post("/clock", json={"sim_time": "15:30", "speed": 2}).json()
    assert r["sim"] == t("15:30") and r["speed"] == 2
    rig.wall.t += 60
    assert rig.c.get("/clock").json()["sim"] == pytest.approx(t("15:30") + 2)
    assert rig.c.post("/clock", json={"sim_time": "25:99"}).status_code == 422
    rig.c.post("/clock", json={"speed": 0})
    sim = rig.c.get("/clock").json()["sim"]
    rig.wall.t += 600
    assert rig.c.get("/clock").json()["sim"] == sim  # paused again


def test_customer_messages_need_approval_and_go_stale(rig):
    iid = rig.to_head()
    rig.approve(iid)
    rig.c.post(f"/offers/{rig.inc(iid)['active_offer']['id']}/respond", json={"response": "accept"})
    m = rig.c.post("/messages/D9/approve").json()
    assert m["approved"] and "cannot deliver" in m["text"]
    assert next(x for x in rig.c.get("/messages").json()["messages"] if x["delivery_id"] == "D9")["approved"]
    assert rig.c.post("/messages/D1/approve").status_code == 404  # D1 did not change
    assert "customer_message_approved" in rig.actions()


def test_events_stream_carries_incident_and_notification_updates(rig):
    q = rig.app.state.bus.subscribe()
    iid = rig.to_head()
    rig.approve(iid)
    kinds = set()
    while not q.empty():
        kinds.add(q.get_nowait()["type"])
    assert {"incident", "notify", "audit"} <= kinds
