from candyops.model import Run
from candyops.simulation import Logs, new_state, plan_recovery, step_day

from conftest import D0, D1, D2, tiny_inputs


def test_transfer_respects_lead_time_and_dispatch_factory():
    inputs = tiny_inputs(plan_runs=[], opening_raw={("F2", "ING"): 10_000.0, ("F2", "WRAP"): 10_000.0})
    run = Run("T0", D0, "F2", "L2", "X", 5.0, "transfer", 1, ship_to="F1")
    state, logs = new_state(inputs), Logs()
    step_day(state, inputs, D0, [run], {}, "T", logs)
    # 500 total, 450 good shipped; not usable at F1 on D0 even though order A (due D0) is open
    assert state.fg[("F1", "X")] == 0 and state.fg[("F2", "X")] == 0
    assert state.remaining["A"] == 450
    assert logs.transfers[0]["arrival_date"] == D1
    step_day(state, inputs, D1, [], {}, "T", logs)
    # arrives D1: A's deadline has passed, so it goes to B (due D2)
    assert state.remaining == {"A": 450, "B": 50}
    assert sum(f["transfer_in_bags"] for f in logs.finished_goods) == 450


def test_planner_skips_transfer_slots_that_arrive_too_late():
    inputs = tiny_inputs(plan_runs=[], opening_raw={("F2", "ING"): 10_000.0, ("F2", "WRAP"): 10_000.0})
    snap = new_state(inputs)
    runs, slots = plan_recovery(snap, inputs, "transfer", [], {}, "T")
    # Order A (due D0) cannot be helped by a 1-day transfer; order B (due D2) can, from D0 or D1 only.
    assert all(r.date in (D0, D1) and r.ship_to == "F1" for r in runs)
    assert sum(r.hours for r in runs) > 0
    late = [s for s in slots if s["date"] == D2]
    assert late and not late[0]["timing_eligible"]


def test_overtime_planner_stays_within_limits_and_skips_down_lines():
    from datetime import datetime
    from candyops.model import Order
    # B needs 1500 good bags by D2; baseline D1 gives 900, so overtime is required (A on D0 is unrecoverable).
    inputs = tiny_inputs(opening_raw={("F1", "ING"): 10_000.0, ("F1", "WRAP"): 10_000.0},
                         orders=[Order("A", "c", "F1", "X", 450, D0, datetime(2026, 10, 1, 9)),
                                 Order("B", "c", "F1", "X", 1500, D2, datetime(2026, 10, 1, 10))])
    downtime = {("L1", D0): 10.0}
    baseline = list(inputs.plan_runs)
    runs, _ = plan_recovery(new_state(inputs), inputs, "overtime", baseline, downtime, "T")
    assert runs, "expected overtime to be planned for order B"
    assert all(r.date != D0 for r in runs)
    per_day = {}
    for r in runs:
        per_day[(r.line_id, r.date)] = per_day.get((r.line_id, r.date), 0) + r.hours
    assert all(h <= 2.0 for h in per_day.values())


def test_recovery_cannot_take_material_reserved_for_baseline():
    from candyops.simulation import make_reserve
    # F1 has film for exactly one 10 h baseline run tomorrow; an overtime run today must leave it alone.
    inputs = tiny_inputs(opening_raw={("F1", "ING"): 10_000.0, ("F1", "WRAP"): 1000.0}, purchase_orders=[])
    baseline = [Run("R1", D1, "F1", "L1", "X", 10.0)]
    reserve = make_reserve(inputs, baseline, {})
    assert reserve("F1", "WRAP", D0) == 1000
    ot = Run("OT", D0, "F1", "L1", "X", 2.0, "overtime", 100)
    state, logs = new_state(inputs), Logs()
    step_day(state, inputs, D0, [ot], {}, "T", logs, reserve=reserve)
    assert logs.production[0]["total_bags"] == 0
    step_day(state, inputs, D1, baseline, {}, "T", logs, reserve=reserve)
    assert logs.production[1]["total_bags"] == 1000
