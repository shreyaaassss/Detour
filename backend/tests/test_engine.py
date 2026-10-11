import csv

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from detour.engine.models import Closure, Delivery, Location, Scenario, Vehicle
from detour.engine.scenario import demo_scenario, derive_matrix, load_csv_dir, load_json
from detour.engine.solver import _construct, _State, solve
from detour.engine.travel import TravelModel


def check_plan(sc: Scenario, plan):
    seen = []
    for r in plan.routes:
        v = sc.vehicle(r.vehicle_id)
        assert r.initial_load <= v.capacity
        load = r.initial_load
        for s in r.stops:
            d = sc.delivery(s.delivery_id)
            load -= d.size
            assert s.load_after == load >= 0
            assert s.arrival <= d.window_end
            assert s.service_start >= d.window_start
            assert s.arrival + s.wait == pytest.approx(s.service_start)
            assert s.departure == pytest.approx(s.service_start + d.service_time)
            seen.append(s.delivery_id)
    seen += [u.delivery_id for u in plan.unplaced]
    assert sorted(seen) == sorted(d.id for d in sc.deliveries)


def tiny(deliveries, vehicles=None, closures=()):
    locs = [Location(id="depot", name="Depot", x=0, y=0), Location(id="a", name="A", x=20, y=0),
            Location(id="b", name="B", x=0, y=40)]
    vehicles = vehicles or [Vehicle(id="V1", capacity=30, start_location="depot")]
    return Scenario(name="t", depot="depot", day_start=480, locations=locs, vehicles=vehicles,
                    deliveries=deliveries, matrix=derive_matrix(locs), closures=list(closures))


def test_demo_plan_valid_and_complete():
    sc = demo_scenario()
    plan = solve(sc)
    check_plan(sc, plan)
    assert plan.unplaced == []
    assert any(s.wait > 0 for r in plan.routes for s in r.stops)  # waiting is shown


def test_deterministic():
    assert solve(demo_scenario()) == solve(demo_scenario())


def test_local_search_not_worse_than_construction():
    sc = demo_scenario()
    state = _State(sc, TravelModel(sc.matrix))
    _construct(state, sorted(sc.deliveries, key=lambda d: (d.window_end, not d.priority, -d.size, d.id)))
    assert solve(sc).total_travel <= state.total() + 1e-9


def test_unplaceable_too_big():
    plan = solve(tiny([Delivery(id="X", location="a", size=99, window_start=480, window_end=900)]))
    assert "larger than the biggest vehicle capacity" in plan.unplaced[0].reason


def test_unplaceable_window_closes_before_arrival():
    # depot->a is 10 min; day starts 08:00 so earliest arrival 08:10, window closes 08:05
    plan = solve(tiny([Delivery(id="X", location="a", size=5, window_start=480, window_end=485)]))
    assert "earliest any vehicle can arrive is 08:10" in plan.unplaced[0].reason


def test_unplaceable_vehicles_full():
    ds = [Delivery(id="A1", location="a", size=25, window_start=480, window_end=900),
          Delivery(id="A2", location="a", size=25, window_start=480, window_end=900)]
    plan = solve(tiny(ds))
    assert len(plan.unplaced) == 1
    assert "too full" in plan.unplaced[0].reason


def test_unplaceable_window_conflict():
    # both only reachable in the same short window at far apart places: one must be dropped
    ds = [Delivery(id="A1", location="a", size=5, window_start=490, window_end=495, service_time=30),
          Delivery(id="B1", location="b", size=5, window_start=490, window_end=500, service_time=30)]
    plan = solve(tiny(ds))
    assert len(plan.unplaced) == 1
    assert "window" in plan.unplaced[0].reason


def test_closure_only_inside_period():
    tm = TravelModel({"a": {"b": 10}, "b": {"a": 10}}, [Closure(a="a", b="b", start=100, end=200, added_minutes=15)])
    assert tm.travel("a", "b", 99) == 10
    assert tm.travel("a", "b", 100) == 25
    assert tm.travel("b", "a", 150) == 25  # both directions
    assert tm.travel("a", "b", 200) == 10  # end is exclusive
    tm2 = TravelModel({"a": {"b": 10}, "b": {"a": 10}}, [Closure(a="a", b="b", start=0, end=50, multiplier=3)])
    assert tm2.travel("a", "b", 10) == 30


def test_unknown_location_rejected():
    with pytest.raises(ValidationError):
        tiny([Delivery(id="X", location="nowhere", size=5, window_start=480, window_end=900)])


def test_json_roundtrip(tmp_path):
    sc = demo_scenario()
    p = tmp_path / "s.json"
    p.write_text(sc.model_dump_json())
    assert load_json(p) == sc


def test_csv_load(tmp_path):
    def w(name, header, rows):
        with open(tmp_path / name, "w", newline="") as fh:
            c = csv.writer(fh)
            c.writerow(header)
            c.writerows(rows)

    w("locations.csv", ["id", "name", "x", "y"], [["depot", "Depot", 0, 0], ["a", "A", 20, 0]])
    w("vehicles.csv", ["id", "capacity", "driver"], [["V1", 30, "Asha"]])
    w("deliveries.csv", ["id", "location", "size", "window_start", "window_end", "service_time", "priority"],
      [["D1", "a", 10, "08:30", "10:00", 5, "yes"]])
    sc = load_csv_dir(tmp_path, "csv", "depot")
    plan = solve(sc)
    check_plan(sc, plan)
    assert plan.unplaced == [] and sc.deliveries[0].priority


@settings(max_examples=40, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(1, 30), st.integers(0, 4), st.integers(0, 300), st.integers(10, 300)),
        min_size=1, max_size=10,
    )
)
def test_random_plans_always_valid(items):
    locs = [Location(id=f"L{i}", name=f"L{i}", x=i * 13 % 50, y=i * 29 % 50) for i in range(5)]
    ds = [Delivery(id=f"D{i}", location=f"L{loc}", size=size, window_start=480 + ws, window_end=480 + ws + width)
          for i, (size, loc, ws, width) in enumerate(items)]
    vs = [Vehicle(id="V1", capacity=40, start_location="L0"), Vehicle(id="V2", capacity=25, start_location="L0")]
    sc = Scenario(name="r", depot="L0", day_start=480, locations=locs, vehicles=vs, deliveries=ds,
                  matrix=derive_matrix(locs))
    check_plan(sc, solve(sc))
