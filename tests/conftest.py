from datetime import date, datetime, timedelta

import pytest

from candyops.model import Inputs, Order, Run
from candyops.pipeline import run_local

D0 = date(2026, 10, 27)
D1 = D0 + timedelta(days=1)
D2 = D0 + timedelta(days=2)


@pytest.fixture(scope="session")
def pipeline():
    return run_local()


def tiny_inputs(**over) -> Inputs:
    """Hand-checkable world: one SKU 'X' = 0.5 kg ING + 1 WRAP; line L1 makes 100 bags/h at 90 % yield.

    Factory F1 owns L1 and dispatches all orders. Factory F2 owns L2 (same rate/yield) for transfer tests.
    """
    base = dict(
        days=[D0, D1, D2],
        decision_date=D0,
        factories={"F1": {"factory_id": "F1"}, "F2": {"factory_id": "F2"}},
        lines={"L1": "F1", "L2": "F2"},
        capability={("L1", "X"): (100.0, 0.9), ("L2", "X"): (100.0, 0.9)},
        calendar={(l, d): (10.0, 2.0) for l in ("L1", "L2") for d in (D0, D1, D2)},
        downtime_minor={},
        downtime_breakdown={},
        recipes={"X": {"ING": 0.5, "WRAP": 1.0}},
        materials={"ING": {"uom": "kg", "category": "ingredient", "std_cost_usd_per_uom": 1.0},
                   "WRAP": {"uom": "pcs", "category": "seasonal_packaging", "std_cost_usd_per_uom": 0.1}},
        products={"X": {"wholesale_price_usd": 5.0}},
        opening_raw={("F1", "ING"): 300.0, ("F1", "WRAP"): 500.0, ("F2", "ING"): 1000.0, ("F2", "WRAP"): 1000.0},
        opening_fg={("F1", "X"): 0, ("F2", "X"): 0},
        purchase_orders=[{"po_id": "PO1", "factory_id": "F1", "material_id": "WRAP", "qty": 1000.0,
                          "arrival_date": D1}],
        orders=[Order("A", "c", "F1", "X", 450, D0, datetime(2026, 10, 1, 9)),
                Order("B", "c", "F1", "X", 500, D2, datetime(2026, 10, 1, 10))],
        plan_runs=[Run("R0", D0, "F1", "L1", "X", 10.0), Run("R1", D1, "F1", "L1", "X", 10.0)],
        actuals=[],
        params={"overtime_cost_per_line_hour": 100.0, "alternate_run_cost_per_line_hour": 50.0,
                "transfer_cost_per_bag": 0.1, "transfer_lead_time_days": 1.0, "markdown_assumption_pct": 0.5},
        affected_line="L1",
        affected_factory="F1",
    )
    base.update(over)
    return Inputs(**base)
