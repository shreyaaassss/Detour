import ast
import copy
import pathlib

from hypothesis import given, settings
from hypothesis import strategies as st

from detour.engine.models import Closure, Delivery, Location, Scenario, Vehicle
from detour.engine.scenario import demo_scenario, derive_matrix
from detour.engine.solver import solve
from detour.engine.travel import TravelModel
from detour.validator import validate


def fixture():
    sc = demo_scenario()
    plan = solve(sc)
    return sc.model_dump(), plan.model_dump()


def route_with_stops(plan, n=2):
    return next(r for r in plan["routes"] if len(r["stops"]) >= n)


def test_solver_plans_validate():
    s, p = fixture()
    rep = validate(s, p)
    assert rep.valid, rep.violations
    assert rep.checks  # the UI lists what was checked


def test_validator_does_not_import_engine():
    for path in pathlib.Path("detour/validator").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [("." * node.level) + (node.module or "")]
            else:
                continue
            for m in mods:
                assert not m.startswith("detour") and not m.startswith(".."), f"{path.name} imports {m}"


def test_catches_overload():
    s, p = fixture()
    s["vehicles"][0]["capacity"] = 1
    rep = validate(s, p)
    assert "CAPACITY" in rep.codes()


def test_catches_late_arrival():
    s, p = fixture()
    r = route_with_stops(p)
    d = next(d for d in s["deliveries"] if d["id"] == r["stops"][0]["delivery_id"])
    d["window_end"] = r["stops"][0]["arrival"] - 5
    assert "WINDOW_LATE" in validate(s, p).codes()


def test_catches_service_before_window_opens():
    s, p = fixture()
    r = route_with_stops(p)
    r["stops"][0]["service_start"] = 0
    assert "WINDOW_EARLY" in validate(s, p).codes()


def test_catches_tampered_times():
    s, p = fixture()
    r = route_with_stops(p)
    r["stops"][0]["arrival"] -= 20
    rep = validate(s, p)
    assert "TIME_MISMATCH" in rep.codes() and not rep.valid


def test_catches_tampered_load():
    s, p = fixture()
    r = route_with_stops(p)
    r["stops"][0]["load_after"] += 1
    assert "LOAD_MISMATCH" in validate(s, p).codes()


def test_catches_ignored_closure():
    s, p = fixture()
    r = route_with_stops(p)
    first = r["stops"][0]
    closure = {"a": r["start_location"], "b": first["location"], "start": 0, "end": 2000, "added_minutes": 30}
    # plan was built without the closure, so it must now be flagged
    rep = validate(s, p, extra_closures=[closure])
    assert "CLOSURE_IGNORED" in rep.codes()


def test_plan_built_with_closure_validates():
    sc = demo_scenario()
    closure = Closure(a="depot", b="camp", start=0, end=2000, added_minutes=25)
    plan = solve(sc, TravelModel(sc.matrix, [closure]))
    assert validate(sc.model_dump(), plan.model_dump(), extra_closures=[closure.model_dump()]).valid


def test_catches_duplicate_delivery():
    s, p = fixture()
    r = route_with_stops(p)
    other = next(x for x in p["routes"] if x is not r)
    other["stops"].append(copy.deepcopy(r["stops"][0]))
    assert "DUPLICATE_DELIVERY" in validate(s, p).codes()


def test_catches_missing_delivery():
    s, p = fixture()
    r = route_with_stops(p)
    r["stops"].pop()
    assert "MISSING_DELIVERY" in validate(s, p).codes()


def test_unplaced_counts_as_accounted():
    s, p = fixture()
    r = route_with_stops(p)
    gone = r["stops"].pop()
    p["unplaced"].append({"delivery_id": gone["delivery_id"], "reason": "test"})
    assert "MISSING_DELIVERY" not in validate(s, p).codes()


def test_unknown_vehicle_and_delivery():
    s, p = fixture()
    p["routes"][0]["vehicle_id"] = "V99"
    p["routes"][1]["stops"][0]["delivery_id"] = "D99"
    codes = validate(s, p).codes()
    assert {"UNKNOWN_VEHICLE", "UNKNOWN_DELIVERY"} <= codes


def test_shift_end():
    s, p = fixture()
    r = route_with_stops(p)
    vid = r["vehicle_id"]
    next(v for v in s["vehicles"] if v["id"] == vid)["shift_end"] = r["stops"][0]["departure"] - 1
    assert "SHIFT_END" in validate(s, p).codes()


def test_failed_vehicle_cannot_have_later_stops():
    s, p = fixture()
    r = route_with_stops(p)
    first = r["stops"][0]
    # fails right after the first stop; later stops are illegal
    rep = validate(s, p, failures=[{"vehicle_id": r["vehicle_id"], "time": first["departure"] + 1}])
    assert "FAILED_VEHICLE_STOP" in rep.codes()
    assert all(v.delivery_id != first["delivery_id"] for v in rep.violations if v.code == "FAILED_VEHICLE_STOP")


def test_failed_vehicle_stop_in_progress_needs_freezing():
    s, p = fixture()
    r = route_with_stops(p)
    first = r["stops"][0]
    mid = (first["arrival"] + first["departure"]) / 2
    assert "FAILED_VEHICLE_STOP" in validate(s, p, failures=[{"vehicle_id": r["vehicle_id"], "time": mid}]).codes()
    first["frozen"] = True
    rep = validate(s, p, frozen={r["vehicle_id"]: [first]}, failures=[{"vehicle_id": r["vehicle_id"], "time": mid}])
    assert all(v.delivery_id != first["delivery_id"] for v in rep.violations if v.code == "FAILED_VEHICLE_STOP")


def test_frozen_stops_must_be_unchanged():
    s, p = fixture()
    r = route_with_stops(p)
    done = copy.deepcopy(r["stops"][0])
    done["frozen"] = True
    r["stops"][0]["frozen"] = True
    assert "FROZEN_CHANGED" not in validate(s, p, frozen={r["vehicle_id"]: [done]}).codes()
    done["arrival"] += 3  # history says it was done at a different time
    assert "FROZEN_CHANGED" in validate(s, p, frozen={r["vehicle_id"]: [done]}).codes()


def test_frozen_must_be_prefix():
    s, p = fixture()
    r = route_with_stops(p)
    r["stops"][1]["frozen"] = True
    assert "FROZEN_NOT_PREFIX" in validate(s, p).codes()


def test_frozen_stop_reordered_detected():
    s, p = fixture()
    r = route_with_stops(p)
    done = copy.deepcopy(r["stops"][0])
    r["stops"][0]["frozen"] = True
    r["stops"][0], r["stops"][1] = r["stops"][1], r["stops"][0]
    assert "FROZEN_CHANGED" in validate(s, p, frozen={r["vehicle_id"]: [done]}).codes()


@settings(max_examples=40, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(1, 30), st.integers(0, 4), st.integers(0, 300), st.integers(10, 300)),
        min_size=1,
        max_size=10,
    ),
    st.integers(0, 60),
)
def test_every_solver_plan_passes_validator(items, extra):
    locs = [Location(id=f"L{i}", name=f"L{i}", x=i * 13 % 50, y=i * 29 % 50) for i in range(5)]
    ds = [
        Delivery(id=f"D{i}", location=f"L{loc}", size=size, window_start=480 + ws, window_end=480 + ws + width)
        for i, (size, loc, ws, width) in enumerate(items)
    ]
    vs = [Vehicle(id="V1", capacity=40, start_location="L0"), Vehicle(id="V2", capacity=25, start_location="L0")]
    closure = Closure(a="L0", b="L1", start=480, end=600, added_minutes=extra)
    sc = Scenario(
        name="r", depot="L0", day_start=480, locations=locs, vehicles=vs, deliveries=ds,
        matrix=derive_matrix(locs), closures=[closure],
    )
    plan = solve(sc)
    rep = validate(sc.model_dump(), plan.model_dump())
    assert rep.valid, rep.violations
