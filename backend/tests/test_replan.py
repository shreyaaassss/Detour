import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from detour.engine.diff import build_diff
from detour.engine.disruptions import DisruptionError, RoadClosure, UrgentDelivery, VehicleFailure
from detour.engine.models import parse_hhmm as t
from detour.engine.replan import replan
from detour.engine.scenario import DEMO_BASELINE, demo_presets, demo_scenario
from detour.engine.solver import plan_from_sequences
from detour.validator import validate

SC = demo_scenario()
BASE = plan_from_sequences(SC, DEMO_BASELINE)
PRESETS = demo_presets()


def run(name, scenario=SC, plan=BASE):
    return replan(scenario, plan, PRESETS[name])


def stops_by_vehicle(plan):
    return {r.vehicle_id: r.stops for r in plan.routes}


def delivered_once(res):
    ids = [s.delivery_id for r in res.plan.routes for s in r.stops if s.kind == "delivery"]
    ids += [u.delivery_id for u in res.plan.unplaced]
    assert sorted(ids) == sorted(d.id for d in res.scenario.deliveries)


def test_baseline_is_valid():
    assert validate(SC.model_dump(), BASE.model_dump()).valid
    assert BASE.unplaced == []


@pytest.mark.parametrize("name", ["vehicle_failure", "road_closure", "urgent_delivery"])
def test_presets_valid_complete_and_deterministic(name):
    a, b = run(name), run(name)
    assert a.plan == b.plan
    assert a.report.valid
    delivered_once(a)


@pytest.mark.parametrize("name", ["vehicle_failure", "road_closure", "urgent_delivery"])
def test_completed_stops_stay_fixed(name):
    res = run(name)
    before, after = stops_by_vehicle(BASE), stops_by_vehicle(res.plan)
    for vid, old in before.items():
        done = [s for s in old if s.arrival <= res.now]
        new = after[vid][: len(done)]
        assert [(s.delivery_id, s.arrival, s.departure) for s in done] == [
            (s.delivery_id, s.arrival, s.departure) for s in new
        ]
        assert all(s.frozen for s in new)


def test_vehicle_failure_story():
    res = run("vehicle_failure")
    # Ravi's van gets nothing after the breakdown
    assert [s.delivery_id for s in res.plan.route("V2").stops] == ["D1"]
    diff = build_diff(BASE, res.plan, res.scenario, [res.cause], res.now)
    d7 = diff.change("D7")
    assert d7.status == "moved" and d7.old_vehicle == "V2" and d7.new_vehicle == "V4"
    assert d7.new_service == t("14:50")  # Meera: reaches Hadapsar 14:15, handover 5, 30 min to Kothrud
    assert "broke down at Hadapsar" in d7.reason
    d9 = diff.change("D9")
    assert d9.status == "broken" and "14:57" in d9.reason
    # the rescuer collects at Hadapsar before delivering, with the handover modelled
    v4 = res.plan.route("V4").stops
    pick = next(s for s in v4 if s.kind == "pickup" and s.delivery_id == "D7")
    assert pick.location == "hadapsar" and pick.arrival == t("14:20") or pick.arrival >= t("14:15")
    assert [s.delivery_id for s in v4 if s.kind == "delivery"].index("D7") >= 0
    assert diff.counts["broken"] == 1 and diff.counts["moved"] == 2


def test_failed_vehicle_has_no_stops_after_failure_time():
    res = run("vehicle_failure")
    for s in res.plan.route("V2").stops:
        assert s.arrival <= t("14:05")


def test_rescuer_own_deliveries_stay_feasible():
    res = run("vehicle_failure")
    v4 = [s for s in res.plan.route("V4").stops if s.delivery_id in ("D10",)]
    assert v4 and v4[0].service_start >= t("16:00")  # own later delivery still inside its window


def test_closure_applies_only_inside_its_period():
    res = run("road_closure")
    leg_after = {(s.delivery_id): s for s in res.plan.route("V2").stops}
    # D7 was committed (leg departed 13:50, before the closure) so it is untouched
    assert leg_after["D7"].arrival == t("14:20")
    # the closure is on kothrud-aundh from 14:00: the leg leaving Kothrud at 14:25 is slower
    sc = res.scenario
    assert any(c.a == "kothrud" and c.b == "aundh" and c.start == pytest.approx(t("14:00")) for c in sc.closures)
    diff = build_diff(BASE, res.plan, sc, [res.cause], res.now)
    assert diff.change("D8").status == "moved" and "closure" in diff.change("D8").reason


def test_closure_start_in_the_past_is_clamped_to_now():
    d = RoadClosure(a="kothrud", b="aundh", start=t("13:00"), end=t("16:00"), added_minutes=25, reported_at=t("14:00"))
    res = replan(SC, BASE, d)
    assert res.scenario.closures[-1].start == pytest.approx(t("14:00"))
    assert res.report.valid


def test_urgent_delivery_inserted_with_pickup_at_depot():
    res = run("urgent_delivery")
    diff = build_diff(BASE, res.plan, res.scenario, [res.cause], res.now)
    assert diff.change("D13").status == "new"
    v = diff.change("D13").new_vehicle
    stops = res.plan.route(v).stops
    pk = next(s for s in stops if s.kind == "pickup" and s.delivery_id == "D13")
    assert pk.location == "depot" and pk.service_start >= t("14:05")
    assert diff.counts["moved"] == 0 and diff.counts["broken"] == 0


def test_urgent_delivery_unplaceable_is_reported_with_reason():
    d = UrgentDelivery(
        id="D14", location="baner", size=8, window_start=t("14:05"), window_end=t("14:20"), time=t("14:05")
    )
    res = replan(SC, BASE, d)
    diff = build_diff(BASE, res.plan, res.scenario, [res.cause], res.now)
    c = diff.change("D14")
    assert c.status == "broken" and "earliest any vehicle can arrive" in c.reason
    d = UrgentDelivery(
        id="D15", location="camp", size=500, window_start=t("14:05"), window_end=t("18:00"), time=t("14:05")
    )
    assert "larger than the biggest vehicle capacity" in replan(SC, BASE, d).plan.unplaced[0].reason


def test_every_original_delivery_is_classified_with_a_reason():
    for name in PRESETS:
        res = run(name)
        diff = build_diff(BASE, res.plan, res.scenario, [res.cause], res.now)
        ids = {c.delivery_id for c in diff.changes}
        assert ids == {d.id for d in res.scenario.deliveries}
        assert all(c.status in {"kept", "moved", "broken", "new"} and c.reason for c in diff.changes)


def test_parcels_aboard_a_running_vehicle_never_change_vehicle():
    res = run("road_closure")
    diff = build_diff(BASE, res.plan, res.scenario, [res.cause], res.now)
    assert all(c.old_vehicle == c.new_vehicle for c in diff.changes if c.new_vehicle and c.old_vehicle)


@pytest.mark.parametrize(
    "bad",
    [
        RoadClosure(a="nowhere", b="aundh", start=1, end=2, added_minutes=5),
        RoadClosure(a="kothrud", b="kothrud", start=1, end=2, added_minutes=5),
        RoadClosure(a="kothrud", b="aundh", start=5, end=2, added_minutes=5),
        RoadClosure(a="kothrud", b="aundh", start=1, end=2),
        VehicleFailure(vehicle_id="V9", time=850, location="hadapsar"),
        VehicleFailure(vehicle_id="V2", time=850, location="atlantis"),
        UrgentDelivery(id="X", location="atlantis", size=1, window_start=1, window_end=2, time=850),
        UrgentDelivery(id="D1", location="camp", size=1, window_start=1, window_end=2, time=850),
        UrgentDelivery(id="X", location="camp", size=1, window_start=1, window_end=2, time=850, pickup_location="mars"),
    ],
)
def test_unknown_or_invalid_disruptions_are_rejected(bad):
    with pytest.raises(DisruptionError):
        replan(SC, BASE, bad)


def test_time_cannot_go_backwards_and_failed_vehicle_cannot_fail_twice():
    res = run("vehicle_failure")
    with pytest.raises(DisruptionError):
        replan(
            res.scenario,
            res.plan,
            RoadClosure(
                a="kothrud", b="aundh", start=t("13:00"), end=t("16:00"), added_minutes=5, reported_at=t("13:00")
            ),
        )
    with pytest.raises(DisruptionError):
        replan(res.scenario, res.plan, VehicleFailure(vehicle_id="V2", time=t("14:30"), location="camp"))


def test_chained_disruptions_stay_valid_and_keep_history():
    first = run("vehicle_failure")
    second = replan(
        first.scenario,
        first.plan,
        RoadClosure(a="kothrud", b="baner", start=t("14:30"), end=t("17:00"), added_minutes=10, reported_at=t("14:30")),
    )
    third = replan(
        second.scenario,
        second.plan,
        UrgentDelivery(
            id="D20", location="camp", size=5, window_start=t("15:00"), window_end=t("17:30"), time=t("15:00")
        ),
    )
    for earlier, later in [(first, second), (second, third)]:
        for vid, stops in stops_by_vehicle(earlier.plan).items():
            kept = [s for s in stops if s.frozen]
            assert [(s.delivery_id, s.arrival) for s in kept] == [
                (s.delivery_id, s.arrival) for s in stops_by_vehicle(later.plan)[vid][: len(kept)]
            ]
    assert third.report.valid
    delivered_once(third)


def test_second_failure_rescues_a_rescuer_midway():
    first = run("vehicle_failure")  # V4 now carries D7 and D8
    second = replan(first.scenario, first.plan, VehicleFailure(vehicle_id="V4", time=t("14:30"), location="kondhwa"))
    assert second.report.valid
    assert all(s.arrival <= t("14:30") for s in second.plan.route("V4").stops)
    delivered_once(second)


@settings(max_examples=150, deadline=None)
@given(
    st.lists(
        st.one_of(
            st.tuples(
                st.just("closure"),
                st.sampled_from(["kothrud", "aundh", "baner", "hadapsar", "camp", "depot"]),
                st.sampled_from(["kothrud", "aundh", "baner", "hadapsar", "camp", "viman"]),
                st.integers(0, 60),
                st.integers(5, 40),
            ),
            st.tuples(
                st.just("failure"),
                st.sampled_from(["V1", "V2", "V3", "V4", "V5"]),
                st.sampled_from(["kothrud", "hadapsar", "camp", "depot", "kondhwa"]),
                st.integers(0, 60),
                st.integers(0, 1),
            ),
            st.tuples(
                st.just("urgent"),
                st.sampled_from(["camp", "aundh", "viman", "wanowrie", "baner"]),
                st.integers(2, 20),
                st.integers(0, 60),
                st.integers(20, 150),
            ),
        ),
        min_size=1,
        max_size=4,
    )
)
def test_random_disruption_sequences_always_give_valid_plans(events):
    scenario, plan, clock, n = SC, BASE, t("13:50"), 0
    for ev in events:
        clock += ev[3] if ev[0] != "closure" else ev[3]
        if ev[0] == "closure":
            d = RoadClosure(a=ev[1], b=ev[2], start=clock, end=clock + 90, added_minutes=ev[4], reported_at=clock)
        elif ev[0] == "failure":
            d = VehicleFailure(vehicle_id=ev[1], time=clock, location=ev[2])
        else:
            n += 1
            d = UrgentDelivery(
                id=f"U{n}", location=ev[1], size=ev[2], window_start=clock, window_end=clock + ev[4], time=clock
            )
        try:
            res = replan(scenario, plan, d)
        except DisruptionError:
            continue
        assert res.report.valid
        delivered_once(res)
        broke = d.vehicle_id if isinstance(d, VehicleFailure) else None
        for vid, old in stops_by_vehicle(plan).items():  # history is never rewritten
            # a vehicle that breaks down never reaches the stop it was committed to
            done = [s for s in old if s.arrival <= res.now or (s.frozen and vid != broke)]
            new = stops_by_vehicle(res.plan)[vid][: len(done)]
            assert [(s.delivery_id, s.arrival) for s in done] == [(s.delivery_id, s.arrival) for s in new]
        for v in res.scenario.vehicles:
            if v.status == "failed":
                assert all(s.arrival <= v.failed_at for s in res.plan.route(v.id).stops)
        scenario, plan = res.scenario, res.plan


def test_unplaced_parcel_at_a_breakdown_site_still_needs_its_pickup():
    first = run("vehicle_failure")  # D9 is broken and still at Hadapsar
    assert [u.delivery_id for u in first.plan.unplaced] == ["D9"]
    second = replan(
        first.scenario,
        first.plan,
        UrgentDelivery(
            id="D30", location="camp", size=5, window_start=t("14:10"), window_end=t("17:00"), time=t("14:10")
        ),
    )
    assert second.report.valid and [u.delivery_id for u in second.plan.unplaced] == ["D9"]


def test_unplaceable_parcel_stays_aboard_its_vehicle():
    # both roads into Baner slow down, so V2 can no longer reach D9 in time; D9 stays aboard V2
    c1 = RoadClosure(a="kothrud", b="baner", start=t("14:00"), end=t("16:00"), added_minutes=60, reported_at=t("14:00"))
    c2 = RoadClosure(a="aundh", b="baner", start=t("14:01"), end=t("16:00"), added_minutes=60, reported_at=t("14:01"))
    first = replan(SC, BASE, c1)
    first = replan(first.scenario, first.plan, c2)
    broken = {u.delivery_id: u for u in first.plan.unplaced}
    assert "D9" in broken and broken["D9"].vehicle_id == "V2"
    assert "aboard V2" in broken["D9"].reason
    second = replan(
        first.scenario,
        first.plan,
        UrgentDelivery(
            id="D31", location="camp", size=5, window_start=t("14:10"), window_end=t("17:00"), time=t("14:10")
        ),
    )
    assert second.report.valid
    assert [u.delivery_id for u in second.plan.unplaced] == ["D9"] and second.plan.unplaced[0].vehicle_id == "V2"


def test_rescuer_breaking_down_while_loading_reopens_the_pickup():
    # regression from fuzzing: V1 collects an urgent parcel at the depot and fails at the depot at that moment
    u = UrgentDelivery(
        id="U1", location="camp", size=2, window_start=t("16:29"), window_end=t("17:20"), time=t("16:29")
    )
    first = replan(SC, BASE, VehicleFailure(vehicle_id="V5", time=t("15:35"), location="kothrud"))
    second = replan(first.scenario, first.plan, u)
    carrier = next(r for r in second.plan.routes if "U1" in r.delivery_ids)
    pickup = next(s for s in carrier.stops if s.kind == "pickup" and s.delivery_id == "U1")
    third = replan(
        second.scenario,
        second.plan,
        VehicleFailure(vehicle_id=carrier.vehicle_id, time=pickup.arrival, location="depot"),
    )
    assert third.report.valid
    assert "U1" in {x.delivery_id for r in third.plan.routes for x in r.stops if r.vehicle_id != carrier.vehicle_id} | {
        x.delivery_id for x in third.plan.unplaced
    }


def test_plan_from_sequences_rejects_an_infeasible_assignment():
    with pytest.raises(ValueError):
        plan_from_sequences(SC, {**DEMO_BASELINE, "V2": ["D9", "D7", "D8", "D1"]})


def test_moved_rules():
    from detour.engine.diff import Ref, why_moved

    ref = Ref(
        vehicle={"A": "V1", "B": "V1", "C": "V2"},
        service={"A": 100, "B": 130, "C": 100},
        order={"V1": ["A", "B"], "V2": ["C"]},
    )
    assert why_moved(ref, "A", "V1", 100, ["A", "B"]) is None
    assert why_moved(ref, "A", "V1", 114.9, ["A", "B"]) is None  # under 15 min: kept, shift is shown
    assert why_moved(ref, "A", "V1", 115, ["A", "B"]) == "time"
    assert why_moved(ref, "A", "V1", 85, ["A", "B"]) == "time"
    assert why_moved(ref, "A", "V2", 100, ["C", "A"]) == "vehicle"
    assert why_moved(ref, "A", "V1", 100, ["B", "A"]) == "order"
    assert why_moved(ref, "NEW", "V1", 100, ["A", "B", "NEW"]) is None  # not in the reference plan


def test_reasons_are_plain_language_without_internal_codes():
    for name in PRESETS:
        res = run(name)
        diff = build_diff(BASE, res.plan, res.scenario, [res.cause], res.now)
        for c in diff.changes:
            assert "@" not in c.reason and "None" not in c.reason and "nan" not in c.reason.lower()
