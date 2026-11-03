"""Small hand-checkable example.

Day D0: capacity 10 h * 100 = 1000 bags. ING 300 kg / 0.5 = 600 bags, WRAP 500 pcs = 500 bags -> WRAP binds.
        total 500, good floor(500 * 0.9) = 450, rejects 50. Consumes ING 250 kg, WRAP 500.
        End of day: order A (450, due D0) gets 450 -> fully ready.
Day D1: PO1 brings 1000 WRAP at start of day. ING left 50 kg -> 100 bags -> ING binds.
        total 100, good 90, rejects 10. Consumes ING 50, WRAP 100 -> WRAP closes at 900.
        Order B (500, due D2) gets 90.
Day D2: nothing scheduled. B ends 410 short. A rejected bag still consumed its ingredients and film.
"""

from candyops.simulation import Logs, new_state, step_day

from conftest import D0, D1, D2, tiny_inputs


def run_tiny(inputs):
    state, logs = new_state(inputs), Logs()
    for d in inputs.days:
        step_day(state, inputs, d, [r for r in inputs.plan_runs if r.date == d], {}, "T", logs)
    return state, logs


def test_hand_example_matches_hand_calculation():
    state, logs = run_tiny(tiny_inputs())
    p0, p1 = logs.production
    assert (p0["total_bags"], p0["good_bags"], p0["reject_bags"], p0["limiting_factor"]) == (500, 450, 50, "material:WRAP")
    assert (p1["total_bags"], p1["good_bags"], p1["reject_bags"], p1["limiting_factor"]) == (100, 90, 10, "material:ING")
    assert state.remaining == {"A": 0, "B": 410}
    assert state.raw[("F1", "ING")] == 0
    assert state.raw[("F1", "WRAP")] == 900
    assert state.fg[("F1", "X")] == 0
    alloc = [(a["date"], a["order_id"], a["allocated_bags"]) for a in logs.allocations]
    assert alloc == [(D0, "A", 450), (D1, "B", 90)]


def test_rejects_consume_materials_but_never_fulfil_demand():
    state, logs = run_tiny(tiny_inputs())
    consumed_wrap = sum(m["consumed_qty"] for m in logs.materials if m["material_id"] == "WRAP" and m["factory_id"] == "F1")
    total = sum(p["total_bags"] for p in logs.production)
    good = sum(p["good_bags"] for p in logs.production)
    assert consumed_wrap == total == 600  # film consumed for good AND rejected bags
    assert sum(a["allocated_bags"] for a in logs.allocations) == good == 540


def test_supplier_arrival_cannot_be_consumed_early():
    # Plenty of ING; WRAP is short on D0 and the PO only lands on D1.
    inputs = tiny_inputs(opening_raw={("F1", "ING"): 10_000.0, ("F1", "WRAP"): 200.0})
    state, logs = run_tiny(inputs)
    p0, p1 = logs.production
    assert p0["date"] == D0 and p0["total_bags"] == 200  # D1 delivery not usable on D0
    assert p1["date"] == D1 and p1["total_bags"] == 1000  # usable from its arrival day
    receipts = {(m["date"], m["material_id"]): m["receipts_qty"] for m in logs.materials if m["factory_id"] == "F1"}
    assert receipts[(D0, "WRAP")] == 0 and receipts[(D1, "WRAP")] == 1000


def test_output_after_deadline_is_not_allocated_and_becomes_exposure():
    inputs = tiny_inputs(opening_raw={("F1", "ING"): 10_000.0, ("F1", "WRAP"): 10_000.0})
    inputs.orders[:] = [o for o in inputs.orders if o.order_id == "A"]  # only A, due D0
    state, logs = run_tiny(inputs)
    assert state.remaining["A"] == 0
    assert all(a["date"] <= D0 for a in logs.allocations)
    # D0 good 900 - 450 allocated + D1 good 900 stays as seasonal stock
    assert state.fg[("F1", "X")] == 450 + 900


def test_capacity_and_downtime_limit_output():
    inputs = tiny_inputs(opening_raw={("F1", "ING"): 10_000.0, ("F1", "WRAP"): 10_000.0})
    state, logs = new_state(inputs), Logs()
    step_day(state, inputs, D0, inputs.plan_runs[:1], {("L1", D0): 4.0}, "T", logs)
    p = logs.production[0]
    assert p["available_hours"] == 6.0 and p["total_bags"] == 600
    assert p["lost_equipment_bags"] == 400 and p["limiting_factor"] == "equipment"
    day = logs.line_days[0]
    assert day["runtime_hours"] <= day["standard_hours_available"]
    assert day["overtime_hours_available"] == 2.0  # line up part of the day -> overtime allowed


def test_full_day_breakdown_removes_overtime_too():
    from candyops.simulation import line_windows
    w = line_windows(tiny_inputs(), D0, {("L1", D0): 10.0})["L1"]
    assert w["std"] == 0 and w["ot"] == 0


def test_edf_allocation_with_deterministic_tiebreak():
    from datetime import datetime
    from candyops.model import Order
    inputs = tiny_inputs(opening_fg={("F1", "X"): 100, ("F2", "X"): 0}, plan_runs=[],
                         orders=[Order("Z-late", "c", "F1", "X", 100, D2, datetime(2026, 10, 1)),
                                 Order("B-tie", "c", "F1", "X", 100, D1, datetime(2026, 10, 2)),
                                 Order("A-tie", "c", "F1", "X", 100, D1, datetime(2026, 10, 2))])
    state, logs = run_tiny(inputs)
    assert [(a["order_id"], a["allocated_bags"]) for a in logs.allocations] == [("A-tie", 100)]
    assert state.remaining == {"Z-late": 100, "B-tie": 100, "A-tie": 0}
