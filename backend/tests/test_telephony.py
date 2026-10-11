"""The escalation call, with the phone line faked: what is sent to ElevenLabs, how a conversation is read, and how the
outcome moves the rescue along. Nothing here places a real call."""

import json
import stat
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from detour.api import create_app
from detour.rescue.service import RescueConfig
from detour.rescue.strings import say_all
from detour.telephony import service as tel_service
from detour.telephony.client import Api
from detour.telephony.config import CallSettings, from_env, mask
from detour.telephony.convo import read_conversation
from detour.telephony.service import CallRun, TelephonyService
from detour.telephony.setup import INSTRUCTIONS, agent_body, ensure, tool_config
from detour.voice.client import VoiceError


# --- settings ---
def test_settings_from_the_environment(tmp_path):
    state = tmp_path / "t.json"
    state.write_text(json.dumps({"agent_id": "agent_from_setup", "secret": "s3"}))
    s = from_env(
        {
            "DETOUR_CALLS": "on",
            "ELEVENLABS_API_KEY": "k",
            "ELEVENLABS_PHONE_NUMBER_ID": "pn_1",
            "PHONE_RESCUE_DRIVER": "+91 98765-43210",
            "PHONE_MEERA": "+14155550123",
            "PHONE_HEAD": "+10000000000",
            "PUBLIC_BASE_URL": "https://x.example/",
            "DETOUR_CALL_LANGUAGE": "HI",
        },
        state,
    )
    assert s.enabled and s.agent_id == "agent_from_setup" and s.secret == "s3" and s.language == "hi"
    assert s.public_url == "https://x.example"
    assert s.phone_for("Meera") == "+14155550123"  # a person's own number wins
    assert (
        s.phone_for("Sana") == "+919876543210"
    )  # everyone else gets the shared demo phone, spaces and dashes forgiven
    assert "+10000000000" not in s.phones.values()  # the head's number is not a rescue driver's
    assert s.missing() == []


def test_a_malformed_number_is_reported_by_name_and_never_guessed(tmp_path):
    s = from_env(
        {
            "DETOUR_CALLS": "on",
            "ELEVENLABS_API_KEY": "k",
            "ELEVENLABS_PHONE_NUMBER_ID": "p",
            "PHONE_RESCUE_DRIVER": "9876543210",
        },
        None,
    )
    assert s.bad_numbers == ["PHONE_RESCUE_DRIVER"] and not s.phones
    assert any("PHONE_RESCUE_DRIVER" in m and "international" in m for m in s.missing())
    assert "55512345" not in " ".join(s.missing())


def test_what_is_missing_is_spelled_out():
    miss = CallSettings().missing()
    assert any("DETOUR_CALLS=on" in m for m in miss) and any("ELEVENLABS_API_KEY" in m for m in miss)
    assert (
        any("setup" in m for m in miss)
        and any("PHONE_NUMBER_ID" in m for m in miss)
        and any("number to call" in m for m in miss)
    )


def test_numbers_are_masked_for_display():
    assert mask("+919876543210") == "+91*******210"
    assert "9876" not in mask("+919876543210")


# --- the scripts ---
def test_every_call_script_offers_both_keypad_and_voice():
    facts = {"parcel": "D7", "site": "Hadapsar", "dest": "Kothrud Clinic", "due": "15:00"}
    s = say_all("call_script", **facts)
    assert "press 1 or say confirm" in s["en"] and "press 2 or say no" in s["en"]
    assert "1 दबाएँ या कन्फर्म बोलें" in s["hi"] and "2 दबाएँ या नहीं बोलें" in s["hi"]
    assert "1 दाबा किंवा कन्फर्म म्हणा" in s["mr"] and "2 दाबा किंवा नाही म्हणा" in s["mr"]
    assert all("automated" in s["en"] or "ऑटोमेटेड" in s["hi"] or "स्वयंचलित" in s["mr"] for _ in (0,))
    assert "{" not in "".join(s.values())


# --- reading a conversation ---
def convo(status, *turns):
    return {"status": status, "transcript": list(turns)}


def user(msg):
    return {"role": "user", "message": msg}


def tool(decision, method="voice"):
    return {
        "role": "agent",
        "message": None,
        "tool_calls": [
            {"tool_name": "report_decision", "params_as_json": json.dumps({"decision": decision, "method": method})}
        ],
    }


def test_a_ringing_phone_is_not_yet_answered():
    r = read_conversation(convo("initiated"))
    assert (r.state, r.answered, r.decision) == ("ringing", False, None)


def test_answered_means_the_person_spoke_or_the_call_is_live():
    assert read_conversation(convo("in-progress", user("हेलो"))).state == "in_call"
    assert read_conversation(convo("in-progress")).state == "in_call"


@pytest.mark.parametrize(
    ("decision", "method"),
    [
        ("confirmed", "voice"),
        ("confirmed", "keypad"),
        ("declined", "voice"),
        ("declined", "keypad"),
        ("unclear", "voice"),
    ],
)
def test_the_agents_decision_is_read_from_its_tool_call(decision, method):
    r = read_conversation(convo("in-progress", user("x"), tool(decision, method)))
    assert (r.decision, r.how, r.state) == (decision, method, "ended")


def test_a_decision_reaches_us_even_if_the_webhook_could_not():
    # the transcript records the tool call whether or not our server was reachable, so polling is a safety net
    c = convo(
        "done",
        user("1"),
        {**tool("confirmed", "keypad"), "tool_results": [{"tool_name": "report_decision", "is_error": True}]},
    )
    assert read_conversation(c).decision == "confirmed"


def test_a_keypad_answer_stands_if_the_agent_ended_without_reporting():
    assert (read_conversation(convo("done", user("1"))).decision, read_conversation(convo("done", user("1"))).how) == (
        "confirmed",
        "keypad",
    )
    assert read_conversation(convo("done", user("2"))).decision == "declined"
    assert read_conversation(convo("done", user("12"))).decision is None  # only a lone 1 or 2 counts
    assert read_conversation(convo("in-progress", user("1"))).decision is None  # while live, the agent decides


def test_garbage_in_the_decision_means_unclear_never_yes():
    bad = {
        "role": "agent",
        "tool_calls": [{"tool_name": "report_decision", "params_as_json": json.dumps({"decision": "maybe"})}],
    }
    assert read_conversation(convo("in-progress", user("x"), bad)).decision == "unclear"
    broken = {"role": "agent", "tool_calls": [{"tool_name": "report_decision", "params_as_json": "{not json"}]}
    assert read_conversation(convo("done", user("x"), broken)).decision == "unclear"


def test_a_call_that_ends_with_nobody_there():
    r = read_conversation(convo("failed"))
    assert (r.state, r.answered, r.decision) == ("ended", False, None)


# --- telling the app what happened, once ---
def test_the_run_reports_answered_once_then_the_decision():
    run = CallRun("O-1")
    assert run.next_events(read_conversation(convo("initiated")), 3, 25) == []
    assert run.next_events(read_conversation(convo("in-progress", user("हेलो"))), 6, 25) == [("answered", None)]
    assert run.next_events(read_conversation(convo("in-progress", user("हेलो"))), 7, 25) == []
    assert run.next_events(
        read_conversation(convo("in-progress", user("हेलो"), tool("confirmed", "keypad"))), 9, 25
    ) == [("confirmed", "keypad")]
    assert run.finished


def test_a_decision_on_the_first_look_still_reports_the_pickup_first():
    out = CallRun("O-1").next_events(read_conversation(convo("done", user("1"), tool("confirmed", "keypad"))), 8, 25)
    assert out == [("answered", None), ("confirmed", "keypad")]


def test_an_unanswered_call_and_an_unclear_one_are_different():
    assert CallRun("a").next_events(read_conversation(convo("failed")), 30, 25) == [("no_answer", None)]
    assert CallRun("b").next_events(read_conversation(convo("done", user("hmm"))), 30, 25) == [
        ("answered", None),
        ("unclear", None),
    ]
    assert CallRun("c").next_events(read_conversation(convo("initiated")), 31, 25) == [
        ("no_answer", None)
    ]  # rang past its limit


# --- the ElevenLabs request ---
def api_with(handler) -> Api:
    return Api("secret-key", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_the_call_request_carries_the_engines_script_and_nothing_else():
    seen = {}

    def handler(req):
        seen["path"], seen["key"], seen["body"] = req.url.path, req.headers["xi-api-key"], json.loads(req.content)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "conversation_id": "conv_1", "callSid": "CA1"}
        )

    cid, sid = api_with(handler).place_call(
        "agent_1",
        "pn_1",
        "+919876543210",
        first_message="यह डीटूर की कॉल है",
        language="hi",
        variables={"parcel": "D7", "offer_id": "O-3"},
        ring_seconds=25,
    )
    b = seen["body"]
    assert seen["path"] == "/v1/convai/twilio/outbound-call" and (cid, sid) == ("conv_1", "CA1")
    assert (b["agent_id"], b["agent_phone_number_id"], b["to_number"]) == ("agent_1", "pn_1", "+919876543210")
    assert b["telephony_call_config"] == {"ringing_timeout_secs": 25}
    d = b["conversation_initiation_client_data"]
    assert d["dynamic_variables"] == {"parcel": "D7", "offer_id": "O-3"}
    assert d["conversation_config_override"]["agent"] == {"first_message": "यह डीटूर की कॉल है", "language": "hi"}


@pytest.mark.parametrize(
    "resp",
    [httpx.Response(422, json={"detail": "bad number"}), httpx.Response(200, json={"success": False, "message": "no"})],
)
def test_a_call_that_could_not_be_placed_is_a_voice_error_without_the_key(resp):
    with pytest.raises(VoiceError) as e:
        api_with(lambda r: resp).place_call(
            "a", "p", "+1", first_message="x", language="hi", variables={}, ring_seconds=20
        )
    assert "secret-key" not in e.value.message


# --- placing it for real (against a fake phone line) ---
class FakeLine:
    """Stands in for the ElevenLabs conversation API: a script of conversation states, one per poll."""

    def __init__(self, states, fail_place=False):
        self.states, self.placed, self.polls, self.fail_place = list(states), [], 0, fail_place

    def place_call(self, agent_id, phone_number_id, to_number, **kw):
        if self.fail_place:
            raise VoiceError("Could not reach ElevenLabs.")
        self.placed.append({"to": to_number, "agent": agent_id, **kw})
        return "conv_1", "CA1"

    def signed_url(self, agent_id):
        if self.fail_place:
            raise VoiceError("Could not reach ElevenLabs.")
        return f"wss://example.invalid/{agent_id}?sig=1"

    def conversation(self, cid):
        self.polls += 1
        return self.states[min(self.polls - 1, len(self.states) - 1)]


def ready_settings(**kw) -> CallSettings:
    base = {
        "enabled": True,
        "api_key": "key-abc-123",
        "agent_id": "agent_1",
        "phone_number_id": "pn_1",
        "phones": {"*": "+919876543210"},
    }
    return CallSettings(**{**base, **kw})


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(tel_service, "POLL_SECONDS", 0.01)


def wait_for(cond, seconds=3.0):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def start(tel, **kw):
    got = []
    ok = tel.start(
        "O-1",
        "Meera",
        script="स्क्रिप्ट",
        language="hi",
        variables={"parcel": "D7"},
        ring_seconds=25,
        on_event=lambda o, outcome, how: got.append((outcome, how)),
        is_open=kw.get("is_open", lambda: True),
    )
    return ok, got


def test_a_call_is_placed_and_its_outcome_reported():
    line = FakeLine(
        [
            convo("initiated"),
            convo("in-progress", user("हेलो")),
            convo("in-progress", user("1"), tool("confirmed", "keypad")),
        ]
    )
    tel = TelephonyService(ready_settings(), api=line)
    ok, got = start(tel)
    assert ok and wait_for(lambda: ("confirmed", "keypad") in got)
    assert got == [("answered", None), ("confirmed", "keypad")]
    assert line.placed[0]["to"] == "+919876543210" and line.placed[0]["first_message"] == "स्क्रिप्ट"
    assert line.placed[0]["variables"]["offer_id"] == "O-1" and tel.placed == 1
    assert [h["what"] for h in tel.history][:2] == ["placed", "ended"] or wait_for(
        lambda: tel.history[-1]["what"] == "ended"
    )


def test_a_failed_placement_counts_as_no_answer():
    tel = TelephonyService(ready_settings(), api=FakeLine([], fail_place=True))
    ok, got = start(tel)
    assert ok and wait_for(lambda: got == [("no_answer", None)])


def test_polling_stops_when_the_offer_closes():
    line = FakeLine([convo("in-progress", user("हेलो"))])
    tel = TelephonyService(ready_settings(), api=line)
    open_ = threading.Event()
    open_.set()
    ok, _ = start(tel, is_open=open_.is_set)
    assert wait_for(lambda: line.polls >= 2)
    open_.clear()
    n = line.polls
    time.sleep(0.1)
    assert line.polls <= n + 1


def test_calls_are_refused_unless_everything_is_set_up():
    line = FakeLine([])
    for settings in (
        CallSettings(),
        ready_settings(enabled=False),
        CallSettings(enabled=True, api_key="k", agent_id="a", phone_number_id="p"),
    ):
        tel = TelephonyService(settings, api=line)
        ok, got = start(tel)
        assert not ok and not got and not line.placed
    ok, why = TelephonyService(ready_settings(), api=line).can_call("Meera")
    assert ok and why == ""


def test_a_run_cannot_ring_endlessly():
    tel = TelephonyService(ready_settings(max_calls=2), api=FakeLine([convo("failed")]))
    for _ in range(2):
        assert tel.can_call("Meera")[0]
        tel.start(
            "x",
            "Meera",
            script="s",
            language="hi",
            variables={},
            ring_seconds=5,
            on_event=lambda *a: None,
            is_open=lambda: False,
        )
    ok, why = tel.can_call("Meera")
    assert not ok and "limit of 2" in why


def test_only_listed_numbers_are_ever_called():
    tel = TelephonyService(
        CallSettings(enabled=True, api_key="k", agent_id="a", phone_number_id="p", phones={"meera": "+14155550123"}),
        api=FakeLine([]),
    )
    assert tel.can_call("Meera")[0]
    ok, why = tel.can_call("Sana")
    assert not ok and "no number is listed for Sana" in why


def test_the_status_never_shows_a_full_number_or_the_key():
    st = TelephonyService(ready_settings(), api=FakeLine([])).status()
    shown = json.dumps(st)
    assert st["ready"] and st["numbers"] == {"*": "+91*******210"}
    assert "9876543210" not in shown and "key-abc-123" not in shown


# --- inside the rescue flow ---
class Wall:
    t = 2_000_000.0

    def __call__(self):
        return self.t


class Rig:
    def __init__(self, line, settings=None):
        self.wall, self.queue = Wall(), []
        self.tel = TelephonyService(settings or ready_settings(), api=line, deliver=self.queue.append)
        self.app = create_app(
            None, start_ticker=False, rescue_config=RescueConfig(), wall=self.wall, telephony=self.tel
        )
        self.c = TestClient(self.app)
        self.svc = self.app.state.rescue

    def drain(self, seconds=3.0):
        """Run what the phone thread asked the app to do, on this thread, as the real app would."""
        end = time.time() + seconds
        while time.time() < end:
            while self.queue:
                self.queue.pop(0)()
            if (
                self.state() in ("COMMITTED", "OFFER_PUSHED", "EXHAUSTED")
                and self.iid
                and self.inc()["offers"][-1]["channel"] == "call"
                and self.inc()["offers"][-1]["status"] != "open"
            ):
                return
            time.sleep(0.01)

    iid = None

    def to_call(self):
        self.iid = self.c.post(
            "/incidents/report", json={"driver": "Ravi", "transcript": "broke down near Hadapsar"}
        ).json()["incident"]["id"]
        self.c.post(f"/incidents/{self.iid}/confirm", json={"confirmed": True})
        v = self.c.get(f"/incidents/{self.iid}/proposal").json()["proposal"]["plan_version"]
        self.c.post(
            f"/incidents/{self.iid}/approve",
            json={"approved_by": "head", "shortlist": ["V4", "V3"], "proposal_version": v},
        )
        self.wall.t += 61
        self.svc.tick()  # the 60 seconds are up: the call is placed

    def inc(self):
        return self.c.get(f"/incidents/{self.iid}").json()["incident"]

    def state(self):
        return self.inc()["state"]

    def actions(self):
        return [e["action"] for e in self.c.get("/audit?limit=2000").json()["entries"]]


def test_when_the_app_offer_times_out_the_real_call_is_placed_in_hindi_with_the_engines_script():
    line = FakeLine([convo("initiated")])
    rig = Rig(line)
    rig.to_call()
    assert rig.state() == "CALL_ESCALATED"
    assert wait_for(lambda: line.placed)
    p = line.placed[0]
    assert p["language"] == "hi" and p["to"] == "+919876543210" and p["ring_seconds"] == 25
    assert "ऑटोमेटेड" in p["first_message"] and "हडपसर" in p["first_message"] and "D7" in p["first_message"]
    assert "1 दबाएँ या कन्फर्म बोलें" in p["first_message"]
    assert (
        p["variables"]["parcel"] == "D7"
        and p["variables"]["driver"] == "Meera"
        and p["variables"]["offer_id"].startswith("O-")
    )
    assert "real_call_started" in rig.actions()


def test_pressing_1_on_the_phone_accepts_and_commits():
    line = FakeLine([convo("in-progress", user("हेलो")), convo("in-progress", user("1"), tool("confirmed", "keypad"))])
    rig = Rig(line)
    rig.to_call()
    rig.drain()
    inc = rig.inc()
    assert inc["state"] == "COMMITTED" and inc["claim"]["via"] == "call" and inc["claim"]["how"] == "keypad"
    ev = [e for e in rig.c.get("/audit?limit=2000").json()["entries"] if e["action"] == "call_event"]
    assert [e["details"]["outcome"] for e in ev] == ["answered", "confirmed"] and ev[-1]["details"]["how"] == "keypad"
    assert rig.c.get("/state").json()["report"]["valid"]


def test_saying_no_on_the_phone_moves_to_the_next_driver():
    rig = Rig(FakeLine([convo("in-progress", user("नहीं"), tool("declined", "voice"))]))
    rig.to_call()
    rig.drain()
    inc = rig.inc()
    assert (
        inc["state"] == "OFFER_PUSHED"
        and inc["active_offer"]["driver"] == "Sana"
        and inc["active_offer"]["channel"] == "push"
    )


def test_an_unclear_answer_counts_as_no_response():
    rig = Rig(FakeLine([convo("in-progress", user("हम्म"), tool("unclear"))]))
    rig.to_call()
    rig.drain()
    assert rig.inc()["active_offer"]["driver"] == "Sana"
    assert "unclear" in rig.inc()["offers"][1]["outcome"]


def test_if_the_line_fails_the_app_does_not_hang_waiting():
    rig = Rig(FakeLine([], fail_place=True))
    rig.to_call()
    rig.drain()
    assert rig.inc()["active_offer"]["driver"] == "Sana"


def test_the_simulate_buttons_still_work_alongside_a_real_line():
    rig = Rig(FakeLine([convo("initiated")]))
    rig.to_call()
    off = rig.inc()["active_offer"]
    assert rig.c.post("/telephony/webhook", json={"offer_id": off["id"], "outcome": "confirmed"}).status_code == 200
    assert rig.state() == "COMMITTED"


def test_without_a_phone_line_nothing_is_ever_dialled(tmp_path):
    line = FakeLine([])
    rig = Rig(line, CallSettings())  # calls off
    rig.to_call()
    assert rig.state() == "CALL_ESCALATED" and not line.placed
    assert "real_call_skipped" in rig.actions()


# --- Plan B: the conversation is held in the driver's browser, with no phone line ---
def browser_rig(states, **kw):
    """Calls switched off and no number: only the key and the agent, which is all a browser call needs."""
    return Rig(FakeLine(states, **kw), CallSettings(api_key="key-abc-123", agent_id="agent_1"))


def test_a_browser_call_needs_no_phone_line_or_number():
    rig = browser_rig([])
    st = rig.c.get("/telephony/status").json()
    assert st["browser_ready"] and not st["ready"]
    assert not Rig(FakeLine([]), CallSettings()).tel.browser_missing() == []


def test_the_browser_gets_the_engines_script_and_a_signed_address_never_the_key():
    rig = browser_rig([])
    rig.to_call()
    off = rig.inc()["active_offer"]
    r = rig.c.post(f"/offers/{off['id']}/browser-session", json={"driver": "Meera"})
    assert r.status_code == 200
    j = r.json()
    assert j["signed_url"].startswith("wss://") and "key-abc-123" not in r.text
    assert j["language"] == "hi" and "ऑटोमेटेड" in j["first_message"] and "1 दबाएँ या कन्फर्म बोलें" in j["first_message"]
    assert j["variables"]["offer_id"] == off["id"] and j["variables"]["parcel"] == "D7"


def test_only_the_driver_being_called_may_open_the_browser_call():
    rig = browser_rig([])
    rig.to_call()
    off = rig.inc()["active_offer"]
    assert rig.c.post(f"/offers/{off['id']}/browser-session", json={"driver": "Sana"}).status_code == 403
    assert rig.c.post("/offers/O-999/browser-session", json={}).status_code == 404


def test_a_browser_call_is_refused_when_nothing_is_ringing():
    rig = browser_rig([])
    rig.to_call()
    off = rig.inc()["active_offer"]
    rig.c.post("/telephony/webhook", json={"offer_id": off["id"], "outcome": "declined"})
    r = rig.c.post(f"/offers/{off['id']}/browser-session", json={"driver": "Meera"})
    assert r.status_code == 409 and r.json()["code"] == "offer_closed"


def test_a_browser_call_that_cannot_be_set_up_says_so():
    rig = Rig(FakeLine([]), CallSettings(api_key="k"))  # no agent yet
    rig.to_call()
    off = rig.inc()["active_offer"]
    r = rig.c.post(f"/offers/{off['id']}/browser-session", json={"driver": "Meera"})
    assert r.status_code == 409 and r.json()["code"] == "browser_call_unavailable"
    assert rig.state() == "CALL_ESCALATED"  # the simulate buttons and the timers still apply


def test_accepting_in_the_browser_call_commits_the_rescue():
    rig = browser_rig([convo("in-progress", user("1"), tool("confirmed", "keypad"))])
    rig.to_call()
    off = rig.inc()["active_offer"]
    assert (
        rig.c.post(
            f"/offers/{off['id']}/browser-session/started", json={"driver": "Meera", "conversation_id": "conv_9"}
        ).status_code
        == 200
    )
    assert rig.inc()["active_offer"]["call_state"] == "in_call"
    rig.drain()
    inc = rig.inc()
    assert inc["state"] == "COMMITTED" and inc["claim"]["via"] == "call" and inc["claim"]["how"] == "keypad"
    assert "browser_call_started" in rig.actions()
    assert rig.c.get("/state").json()["report"]["valid"]


def test_declining_in_the_browser_call_moves_to_the_next_driver():
    rig = browser_rig([convo("in-progress", user("नहीं"), tool("declined", "voice"))])
    rig.to_call()
    off = rig.inc()["active_offer"]
    rig.c.post(f"/offers/{off['id']}/browser-session/started", json={"driver": "Meera", "conversation_id": "conv_9"})
    rig.drain()
    assert rig.inc()["active_offer"]["driver"] == "Sana"


def test_a_browser_call_cannot_be_opened_endlessly():
    rig = Rig(FakeLine([]), CallSettings(api_key="k", agent_id="a", max_calls=1))
    rig.to_call()
    off = rig.inc()["active_offer"]
    assert rig.c.post(f"/offers/{off['id']}/browser-session", json={"driver": "Meera"}).status_code == 200
    assert rig.c.post(f"/offers/{off['id']}/browser-session", json={"driver": "Meera"}).status_code == 409


# --- the agent's own webhook ---
def test_the_agents_tool_call_needs_the_shared_secret():
    rig = Rig(FakeLine([convo("initiated")]), ready_settings(secret="shh"))
    rig.to_call()
    off = rig.inc()["active_offer"]
    body = {"offer_id": off["id"], "decision": "confirmed", "method": "keypad"}
    assert rig.c.post("/telephony/agent", json=body).status_code == 401
    assert rig.c.post("/telephony/agent", json=body, headers={"X-Detour-Key": "wrong"}).status_code == 401
    assert rig.state() == "CALL_ESCALATED" and "agent_report_refused" in rig.actions()
    ok = rig.c.post("/telephony/agent", json=body, headers={"X-Detour-Key": "shh"})
    assert ok.status_code == 200 and ok.json() == {"ok": True} and rig.state() == "COMMITTED"
    assert rig.inc()["claim"]["how"] == "keypad"


def test_a_late_report_from_the_agent_is_ignored_calmly():
    rig = Rig(FakeLine([convo("initiated")]), ready_settings(secret="shh"))
    rig.to_call()
    off = rig.inc()["active_offer"]
    rig.c.post("/telephony/webhook", json={"offer_id": off["id"], "outcome": "declined"})
    r = rig.c.post(
        "/telephony/agent", json={"offer_id": off["id"], "decision": "confirmed"}, headers={"X-Detour-Key": "shh"}
    )
    assert r.status_code == 200 and r.json()["ok"] is False  # the agent is not given an error mid-call
    assert rig.inc()["claim"] is None


def test_a_secretless_server_refuses_everything():
    rig = Rig(FakeLine([]), ready_settings())  # no secret configured
    r = rig.c.post("/telephony/agent", json={"offer_id": "O-1", "decision": "confirmed"}, headers={"X-Detour-Key": ""})
    assert r.status_code == 401


def test_status_and_test_call_endpoints():
    rig = Rig(FakeLine([convo("failed")]))
    st = rig.c.get("/telephony/status").json()
    assert st["ready"] and st["language"] == "hi"
    r = rig.c.post("/telephony/test", json={"driver": "Meera"})
    assert r.status_code == 200 and r.json()["started"]
    off = Rig(FakeLine([]), CallSettings())
    refused = off.c.post("/telephony/test")
    assert refused.status_code == 409 and "not set up" in refused.json()["message"]


# --- the agent definition ---
class FakeApi:
    def __init__(self):
        self.calls = []

    def create_tool(self, cfg):
        self.calls.append(("create_tool", cfg))
        return {"id": "tool_1"}

    def update_tool(self, tid, cfg):
        self.calls.append(("update_tool", tid, cfg))
        return {}

    def create_agent(self, body):
        self.calls.append(("create_agent", body))
        return {"agent_id": "agent_1"}

    def update_agent(self, aid, body):
        self.calls.append(("update_agent", aid, body))
        return {}


def test_setup_creates_then_updates_and_keeps_its_secret(tmp_path):
    path = tmp_path / "telephony.json"
    api = FakeApi()
    s = CallSettings(api_key="k", public_url="https://one.example")
    first = ensure(api, s, path)
    assert [c[0] for c in api.calls] == ["create_tool", "create_agent"]
    assert first["agent_id"] == "agent_1" and first["tool_id"] == "tool_1" and first["secret"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600  # it holds the shared secret

    api.calls.clear()
    second = ensure(api, CallSettings(api_key="k", public_url="https://two.example"), path)
    assert [c[0] for c in api.calls] == ["update_tool", "update_agent"]  # nothing is created twice
    assert second["secret"] == first["secret"] and second["agent_id"] == "agent_1"
    assert api.calls[0][2]["api_schema"]["url"] == "https://two.example/telephony/agent"  # a new tunnel is picked up


def test_the_agent_is_built_to_take_one_clear_answer_by_voice_or_keypad():
    body = agent_body("tool_1", "n", "voice1")
    cc = body["conversation_config"]
    assert cc["agent"]["language"] == "hi" and cc["agent"]["prompt"]["tool_ids"] == ["tool_1"]
    assert cc["conversation"]["dtmf_input_settings"]["hash_terminator"] is False  # a lone 1 or 2 must be enough
    assert cc["conversation"]["max_duration_seconds"] <= 150  # long enough to answer a few questions
    assert set(cc["language_presets"]) == {"en", "mr"}
    end = cc["agent"]["prompt"]["built_in_tools"]["end_call"]
    assert end["name"] == "end_call" and end["params"]["system_tool_type"] == "end_call"
    ov = body["platform_settings"]["overrides"]["conversation_config_override"]["agent"]
    assert ov == {"first_message": True, "language": True}  # the engine's script is allowed in per call
    for needle in (
        "automated",
        "Never add, change, guess or promise any fact",
        "presses 1",
        "never ask a third time".capitalize()[:0] or "third time",
        "Never reveal",
        "EXACTLY one of these two sentences",
        "the ONLY facts you know",
        "do not have that information",
    ):
        assert needle in INSTRUCTIONS, needle


def test_the_decision_tool_posts_to_our_endpoint_with_the_secret():
    t = tool_config("https://x.example", "shh")
    api = t["api_schema"]
    assert api["url"] == "https://x.example/telephony/agent" and api["method"] == "POST"
    assert api["request_headers"] == {"X-Detour-Key": "shh"}
    props = api["request_body_schema"]["properties"]
    assert props["offer_id"] == {"type": "string", "dynamic_variable": "offer_id"}  # never chosen by the model
    assert props["decision"]["enum"] == ["confirmed", "declined", "unclear"] and props["method"]["enum"] == [
        "voice",
        "keypad",
    ]
