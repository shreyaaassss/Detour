import json

import pytest
from fastapi.testclient import TestClient

from detour.api import create_app
from detour.engine.models import parse_hhmm as t
from detour.engine.scenario import demo_scenario


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "audit.jsonl")


@pytest.fixture
def c(app):
    return TestClient(app)


def failure_body(**kw):
    d = {"type": "vehicle_failure", "vehicle_id": "V2", "time": t("14:05"), "location": "hadapsar"}
    return {"disruption": {**d, **kw.pop("d", {})}, **kw}


def actions(c):
    return [e["action"] for e in c.get("/audit?limit=2000").json()["entries"]]


def test_starts_with_a_valid_demo_baseline(c):
    s = c.get("/state").json()
    assert s["kind"] == "demo" and s["plan"] and s["report"]["valid"]
    assert s["diff"]["counts"] == {"kept": 12, "moved": 0, "broken": 0, "new": 0}
    assert s["plan"] == s["original"]
    assert {"server_started", "scenario_loaded", "plan_built"} <= set(actions(c))


def test_solver_can_plan_the_demo_scenario_too(c):
    s = c.post("/plan", json={"mode": "solve"}).json()
    assert s["report"]["valid"] and s["plan"]["unplaced"] == []
    assert c.post("/plan", json={"mode": "nope"}).status_code == 422


def test_custom_scenario_flow(c):
    sc = demo_scenario().model_copy(update={"name": "mine"})
    assert c.post("/scenario", json=sc.model_dump()).status_code == 200
    assert c.get("/state").json()["plan"] is None
    assert c.post("/disruptions", json=failure_body()).status_code == 409  # no plan yet
    assert c.post("/plan", json={"mode": "demo"}).status_code == 400  # hand baseline is demo-only
    s = c.post("/plan").json()  # auto -> solver
    assert s["kind"] == "custom" and s["report"]["valid"]


def test_bad_scenario_is_rejected(c):
    bad = demo_scenario().model_dump()
    bad["deliveries"][0]["location"] = "atlantis"
    r = c.post("/scenario", json=bad)
    assert r.status_code == 422 and "atlantis" in json.dumps(r.json())


def test_presets(c):
    p = c.get("/presets").json()
    assert set(p) == {"vehicle_failure", "road_closure", "urgent_delivery"}


def test_preview_changes_nothing_and_shows_the_diff(c):
    before = c.get("/state").json()
    p = c.post("/disruptions/preview", json=failure_body()).json()
    assert p["diff"]["counts"]["moved"] == 2 and p["diff"]["counts"]["broken"] == 1
    assert p["report"]["valid"]
    assert [v["status"] for v in p["scenario"]["vehicles"]].count("failed") == 1  # the proposal can be drawn
    after = c.get("/state").json()
    assert after["plan"] == before["plan"] and after["version"] == before["version"]
    assert "disruption_previewed" in actions(c) and "disruption_applied" not in actions(c)


def test_confirm_applies_exactly_the_previewed_plan(c):
    p = c.post("/disruptions/preview", json=failure_body()).json()
    s = c.post(f"/disruptions/{p['preview_id']}/confirm", json={"confirmed_by": "dispatcher"}).json()
    assert s["plan"] == p["plan"]
    assert s["applied"][0]["confirmed_by"] == "dispatcher" and s["version"] > p["base_version"]
    assert "disruption_applied" in actions(c)
    assert c.post(f"/disruptions/{p['preview_id']}/confirm", json={"confirmed_by": "x"}).status_code == 404


def test_preview_goes_stale_when_the_plan_changes(c):
    a = c.post("/disruptions/preview", json=failure_body()).json()
    closure = {
        "type": "road_closure",
        "a": "kothrud",
        "b": "aundh",
        "start": t("14:00"),
        "end": t("16:00"),
        "added_minutes": 25,
        "reported_at": t("14:00"),
    }
    assert c.post("/disruptions", json={"disruption": closure}).status_code == 200
    r = c.post(f"/disruptions/{a['preview_id']}/confirm", json={"confirmed_by": "dispatcher"})
    assert r.status_code == 404  # applying a change voids every earlier preview
    e = [x for x in c.get("/audit").json()["entries"] if x["action"] == "disruption_refused"]
    assert e and "preview" in e[-1]["details"]["reason"]


def test_apply_failure_preset(c):
    s = c.post("/disruptions", json=failure_body()).json()
    assert [x["delivery_id"] for r in s["plan"]["routes"] if r["vehicle_id"] == "V2" for x in r["stops"]] == ["D1"]
    d7 = next(x for x in s["diff"]["changes"] if x["delivery_id"] == "D7")
    assert d7["status"] == "moved" and d7["new_vehicle"] == "V4" and d7["new_service"] == t("14:50")
    assert s["report"]["valid"] and s["plan"]["as_of"] == t("14:05")
    assert s["original"] != s["plan"]


def test_all_presets_apply_and_validate(c):
    for name, d in c.get("/presets").json().items():
        c.post("/reset")
        s = c.post("/disruptions", json={"disruption": d}).json()
        assert s["report"]["valid"], name
        assert c.post("/validate").json()["valid"], name


def test_presets_are_reproducible(c):
    def run():
        c.post("/reset")
        return c.post("/disruptions", json=failure_body()).json()["plan"]

    assert run() == run()


def test_interpreted_report_needs_confirmation(c):
    body = failure_body(d={"source": "text"})
    r = c.post("/disruptions", json=body)
    assert r.status_code == 422 and r.json()["code"] == "confirmation_required"
    assert c.get("/state").json()["applied"] == []
    assert "disruption_refused" in actions(c)
    assert c.post("/disruptions", json={**body, "confirmed_by": "dispatcher"}).status_code == 200


def test_unknown_location_is_rejected_and_logged(c):
    before = c.get("/state").json()
    r = c.post("/disruptions", json=failure_body(d={"location": "Atlantis"}))
    assert r.status_code == 422 and "Atlantis" in r.json()["message"]
    assert c.get("/state").json()["plan"] == before["plan"]
    refused = [e for e in c.get("/audit").json()["entries"] if e["action"] == "disruption_refused"]
    assert refused and "Atlantis" in refused[-1]["details"]["reason"]


def test_malformed_disruption_is_422(c):
    assert c.post("/disruptions", json={"disruption": {"type": "meteor"}}).status_code == 422


def test_validate_endpoint_catches_a_tampered_plan(c):
    assert c.post("/validate").json()["valid"]
    plan = c.get("/plan").json()["plan"]
    plan["routes"][0]["stops"][0]["arrival"] += 120
    r = c.post("/validate", json={"plan": plan}).json()
    assert not r["valid"] and r["violations"]
    assert [e for e in c.get("/audit").json()["entries"] if e["action"] == "validation_run"][-1]["details"][
        "supplied_plan"
    ]


def test_audit_records_who_did_what_and_chain_verifies(c):
    c.post("/disruptions", json=failure_body(), headers={"X-Actor": "dispatcher-asha"})
    entries = c.get("/audit").json()
    applied = next(e for e in entries["entries"] if e["action"] == "disruption_applied")
    assert applied["actor"] == "dispatcher-asha" and applied["sim_time"] == t("14:05")
    assert entries["chain"]["valid"] and c.get("/audit/verify").json()["valid"]
    assert [e["id"] for e in entries["entries"]] == list(range(1, len(entries["entries"]) + 1))


def test_audit_survives_restart(tmp_path):
    p = tmp_path / "audit.jsonl"
    first = TestClient(create_app(p))
    first.post("/disruptions", json=failure_body())
    n = first.get("/audit").json()["total"]
    second = TestClient(create_app(p))
    assert second.get("/audit").json()["total"] > n and second.get("/audit/verify").json()["valid"]


def test_reset_restores_the_baseline(c):
    c.post("/disruptions", json=failure_body())
    s = c.post("/reset").json()
    assert s["applied"] == [] and s["plan"] == s["original"]
    assert c.get("/audit/verify").json()["valid"]  # the history is kept, not erased


def test_diff_endpoint(c):
    assert c.get("/plan/diff").json()["counts"]["kept"] == 12
    c.post("/disruptions", json=failure_body())
    d = c.get("/plan/diff").json()
    assert d["counts"]["broken"] == 1 and all(x["reason"] for x in d["changes"])


def test_events_are_published_on_changes(app, c):
    q = app.state.bus.subscribe()
    c.post("/disruptions", json=failure_body())
    kinds = []
    while not q.empty():
        kinds.append(q.get_nowait()["type"])
    assert "state" in kinds and "audit" in kinds


def test_sse_stream_sends_hello(c):
    with c.stream("GET", "/events?max_events=1") as r:
        text = "".join(r.iter_text())
    assert r.headers["content-type"].startswith("text/event-stream")
    assert text.startswith("event: hello") and '"version"' in text
