import re
import time

from fastapi.testclient import TestClient

from detour.api import create_app
from detour.engine.scenario import demo_scenario
from detour.messages import _cause
from detour.rescue.clock import SimClock
from detour.rescue.extract import extract
from detour.rescue.service import RescueConfig
from detour.rescue.strings import LANGS, TEXT, local_names, say_all

SC = demo_scenario()


def test_extraction_finds_one_known_place_and_the_breakdown():
    e = extract("My truck broke down near Hadapsar and I can't make the 3 PM delivery.", SC)
    assert e.location_id == "hadapsar" and e.breakdown


def test_extraction_matches_whole_words_only():
    assert extract("engine trouble at the campus", SC).location_ids == []  # "camp" is not "campus"
    assert extract("engine trouble at Camp", SC).location_ids == ["camp"]


def test_extraction_uses_devanagari_names_and_never_guesses():
    assert extract("गाडी कोथरूड जवळ बंद पडली", SC).location_id == "kothrud"
    assert extract("गाडी कोथरूड आणि औंध मध्ये", SC).location_id is None  # two places: ambiguous, so not chosen
    assert extract("broke down somewhere", SC).location_ids == []
    assert not extract("running a bit late near Aundh", SC).breakdown


def test_every_message_exists_in_every_language_with_no_loose_braces():
    facts = {
        "place": "P",
        "parcel": "D7",
        "due": "15:00",
        "driver": "A",
        "vehicle": "V1",
        "eta": "14:15",
        "site": "S",
        "dest": "T",
    }
    for key, table in TEXT.items():
        assert set(table) == set(LANGS), key
        for lang, text in say_all(key, **facts).items():
            assert "{" not in text and "}" not in text, (key, lang)


def test_the_call_script_stays_short_enough_to_say_in_about_twenty_seconds():
    script = say_all("call_script", parcel="D7", site="Hadapsar", dest="Kothrud Clinic", due="15:00")["en"]
    assert len(re.findall(r"\S+", script)) <= 50  # about 17 seconds at a normal pace
    assert "automated call" in script and "approved" in script  # it says what it is and who approved it


def test_place_names_follow_the_readers_script():
    n = local_names("Hadapsar", ["हडपसर"])
    assert n == {"en": "Hadapsar", "hi": "हडपसर", "mr": "हडपसर"}
    assert local_names("Camp", [])["mr"] == "Camp"


def test_customer_message_causes_read_naturally():
    assert _cause(["vehicle_failure"]) == "a vehicle breakdown"
    assert _cause(["road_closure", "vehicle_failure", "road_closure"]) == "a road closure and a vehicle breakdown"
    assert _cause([]) == "a change to our plan"


def test_the_simulated_clock_pauses_and_runs():
    wall = [1000.0]
    c = SimClock(845, 0, lambda: wall[0])
    wall[0] += 600
    assert c.now() == 845
    c.set(speed=2)
    wall[0] += 60
    assert c.now() == 847
    c.set(900)
    assert c.now() == 900 and c.live
    c.set(speed=0)
    wall[0] += 999
    assert c.now() == 900


def test_the_real_background_timer_escalates_to_a_call():
    cfg = RescueConfig(push_timeout=0.3, ring_timeout=0.3, conversation_limit=0.3)
    app = create_app(None, rescue_config=cfg)
    with TestClient(app) as c:  # entering the client starts the ticker
        iid = c.post("/incidents/report", json={"driver": "Ravi", "transcript": "broke down near Hadapsar"}).json()[
            "incident"
        ]["id"]
        c.post(f"/incidents/{iid}/confirm", json={"confirmed": True})
        v = c.get(f"/incidents/{iid}/proposal").json()["proposal"]["plan_version"]
        c.post(
            f"/incidents/{iid}/approve", json={"approved_by": "head", "shortlist": ["V4", "V3"], "proposal_version": v}
        )
        seen = []
        for _ in range(40):
            time.sleep(0.1)
            st = c.get(f"/incidents/{iid}").json()["incident"]
            if not seen or seen[-1] != st["state"]:
                seen.append(st["state"])
            if st["state"] == "OFFER_PUSHED" and st["current"] == 1:
                break
        assert seen[:3] == ["OFFER_PUSHED", "CALL_ESCALATED", "OFFER_PUSHED"]  # push -> call -> next driver
