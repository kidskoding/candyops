"""Integration tests on the full synthetic CandyOps dataset."""

import copy
from collections import defaultdict

import pytest

from candyops.config import DECISION_DATE
from candyops.pipeline import run_local
from candyops.silver import normalize
from candyops.sources import generate_sources
from candyops.spark_io import fqn, infer_columns
from candyops.validation import check_sources


def test_all_silver_checks_pass(pipeline):
    failed = [c for c in pipeline["silver_checks"] if c["status"] != "PASS"]
    assert not failed, failed


def test_all_gold_integrity_checks_pass(pipeline):
    checks = pipeline["gold"]["gold_validation_results"]
    assert len(checks) > 50
    failed = [c for c in checks if c["status"] != "PASS"]
    assert not failed, failed


def test_silver_checks_expose_bad_data():
    bronze = generate_sources()
    bronze = copy.deepcopy(bronze)
    bronze["erp_customer_orders"][0]["sku_id"] = "NOPE"
    bronze["proc_purchase_orders"][0]["uom"] = "lb"
    bronze["qms_batch_inspections"][0]["good_bags"] = "1"
    bronze["mes_downtime_events"][0]["end_ts"] = bronze["mes_downtime_events"][0]["start_ts"]
    failed = {c["check_name"] for c in check_sources(normalize(bronze)) if c["status"] == "FAIL"}
    assert {"order_refs_exist", "po_uom_matches_material", "good_plus_reject_equals_total",
            "event_end_after_start"} <= failed


def test_deterministic_reruns():
    a, b = run_local(), run_local()
    assert a["bronze"] == b["bronze"]
    assert a["gold"] == b["gold"]


def test_identical_start_state_and_history(pipeline):
    summary = pipeline["gold"]["gold_scenario_summary"]
    assert len({s["start_state_fingerprint"] for s in summary}) == 1
    prod = pipeline["gold"]["gold_daily_line_production"]
    hist = defaultdict(list)
    for p in prod:
        if p["phase"] == "actual":
            assert p["date"] < DECISION_DATE
            hist[p["scenario_id"]].append((p["run_id"], p["total_bags"], p["good_bags"]))
    assert len({tuple(sorted(v)) for v in hist.values()}) == 1


def test_material_and_finished_goods_conservation(pipeline):
    g = pipeline["gold"]
    for m in g["gold_material_balance"]:
        assert abs(m["opening_qty"] + m["receipts_qty"] - m["consumed_qty"] - m["closing_qty"]) < 1e-3
        assert m["closing_qty"] >= -1e-6
    for f in g["gold_finished_goods_balance"]:
        assert f["opening_bags"] + f["transfer_in_bags"] + f["produced_to_stock_bags"] - f["allocated_bags"] \
            == f["closing_bags"] >= 0


def test_no_double_allocation_and_deadlines(pipeline):
    g = pipeline["gold"]
    qty = {(o["scenario_id"], o["order_id"]): o for o in g["gold_order_fulfillment"]}
    total = defaultdict(int)
    for a in g["gold_order_allocations"]:
        o = qty[(a["scenario_id"], a["order_id"])]
        assert a["date"] <= o["ready_to_ship_deadline"]
        assert a["factory_id"] == o["dispatch_factory_id"]
        total[(a["scenario_id"], a["order_id"])] += a["allocated_bags"]
    for k, o in qty.items():
        assert total[k] == o["ready_on_time_bags"] <= o["order_qty_bags"]


def test_capacity_limits(pipeline):
    for d in pipeline["gold"]["gold_daily_line_capacity"]:
        if d["phase"] == "simulated":
            assert d["runtime_standard_hours"] <= d["standard_hours_available"] + 1e-6
            assert d["runtime_overtime_hours"] <= d["overtime_hours_available"] + 1e-6
            assert d["standard_hours_available"] + d["downtime_hours"] == pytest.approx(d["planned_operating_hours"])


def test_transfer_lead_time_in_full_model(pipeline):
    for t in pipeline["gold"]["gold_transfers"]:
        assert (t["arrival_date"] - t["ship_date"]).days == 1
        assert t["to_factory_id"] == "NFD"


def test_breakdown_creates_risk_and_reference_is_clean(pipeline):
    s = {r["scenario_id"]: r for r in pipeline["gold"]["gold_scenario_summary"]}
    assert s["S0_REFERENCE_NO_BREAKDOWN"]["bags_short"] == 0
    assert s["S1_NO_RECOVERY"]["bags_short"] > 0
    at_risk = [o for o in pipeline["gold"]["gold_order_fulfillment"]
               if o["scenario_id"] == "S1_NO_RECOVERY" and o["at_risk_after_breakdown"]]
    assert at_risk and all(o["dispatch_factory_id"] == "NFD" for o in at_risk)
    # recovery options never do worse than no recovery
    for sid in ("S2_OVERTIME", "S3_TRANSFER", "S3B_TRANSFER_EARLY_WRAPPERS"):
        assert s[sid]["bags_ready_on_time"] >= s["S1_NO_RECOVERY"]["bags_ready_on_time"]
        assert s[sid]["incremental_cost_usd"] >= 0


def test_cost_model_has_no_double_counting(pipeline):
    for s in pipeline["gold"]["gold_scenario_summary"]:
        assert s["incremental_cost_usd"] == pytest.approx(
            s["overtime_cost_usd"] + s["alternate_run_cost_usd"] + s["transfer_freight_usd"], abs=0.02)
        if s["scenario_id"] in ("S0_REFERENCE_NO_BREAKDOWN", "S1_NO_RECOVERY"):
            assert s["incremental_cost_usd"] == 0 and s["cost_per_incremental_ready_bag_usd"] is None


def test_sensitivity_is_computed_not_asserted(pipeline):
    sens = pipeline["gold"]["gold_sensitivity"][0]
    assert sens["delta_bags_ready_on_time"] == sens["test_bags_ready_on_time"] - sens["base_bags_ready_on_time"]
    assert ("were binding" in sens["verdict"]) == (sens["delta_bags_ready_on_time"] > 0)


def test_spark_io_helpers_without_spark():
    from datetime import date
    cols = dict(infer_columns([{"a": 1, "b": None, "c": date(2026, 1, 1)}, {"a": 2.5, "b": "x", "c": None}]))
    assert cols == {"a": "double", "b": "string", "c": "date"}
    assert fqn("workspace", "candyops", "gold_x") == "`workspace`.`candyops`.`gold_x`"
    with pytest.raises(ValueError):
        fqn("workspace", "candyops; DROP", "t")


def test_row_order_does_not_change_results(pipeline):
    """Spark collect() returns rows in arbitrary order; gold must not depend on it."""
    import random
    from candyops.pipeline import build_gold
    silver = copy.deepcopy(pipeline["silver"])
    rng = random.Random(7)
    for rows in silver.values():
        rng.shuffle(rows)
    shuffled = build_gold(silver)
    for name in ("gold_scenario_summary", "gold_sensitivity", "gold_validation_results"):
        assert shuffled[name] == pipeline["gold"][name]
    key = lambda r: repr(sorted((k, repr(v)) for k, v in r.items()))
    for name in ("gold_order_fulfillment", "gold_material_balance", "gold_daily_line_production"):
        assert sorted(shuffled[name], key=key) == sorted(pipeline["gold"][name], key=key)
