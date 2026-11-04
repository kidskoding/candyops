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
    def key(r):
        return repr(sorted((k, repr(v)) for k, v in r.items()))
    for name in ("gold_order_fulfillment", "gold_material_balance", "gold_daily_line_production"):
        assert sorted(shuffled[name], key=key) == sorted(pipeline["gold"][name], key=key)


def _summary(pipeline):
    return {s["scenario_id"]: s for s in pipeline["gold"]["gold_scenario_summary"]}


def test_overtime_cap_sweep_matches_scenarios_and_grows(pipeline):
    s = _summary(pipeline)
    caps = [r for r in pipeline["gold"]["gold_sweep"] if r["sweep_name"] == "overtime_cap_hours"]
    by_cap = {r["days_or_hours"]: r for r in caps}
    assert by_cap[0.0]["bags_ready_on_time"] == s["S1_NO_RECOVERY"]["bags_ready_on_time"]
    assert by_cap[0.0]["incremental_cost_usd"] == 0
    assert by_cap[4.0]["bags_ready_on_time"] == s["S2_OVERTIME"]["bags_ready_on_time"]
    assert by_cap[4.0]["incremental_cost_usd"] == s["S2_OVERTIME"]["incremental_cost_usd"]
    bags = [r["bags_ready_on_time"] for r in sorted(caps, key=lambda r: r["days_or_hours"])]
    assert bags == sorted(bags)


def test_earlier_film_never_hurts_and_matches_scenarios(pipeline):
    s = _summary(pipeline)
    sweep = [r for r in pipeline["gold"]["gold_sweep"] if r["sweep_name"] == "film_delivery_date"]
    for option, on_time_oct30, on_time_oct27 in (
            ("transfer", "S3_TRANSFER", "S3B_TRANSFER_EARLY_WRAPPERS"),
            ("overtime+transfer", "S4_OVERTIME_AND_TRANSFER", None)):
        rows = sorted((r for r in sweep if r["option"] == option), key=lambda r: r["days_or_hours"])
        assert [r["param_value"] for r in rows] == ["2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"]
        bags = [r["bags_ready_on_time"] for r in rows]
        assert bags == sorted(bags, reverse=True)
        assert rows[-1]["bags_ready_on_time"] == s[on_time_oct30]["bags_ready_on_time"]
        if on_time_oct27:
            assert rows[0]["bags_ready_on_time"] == s[on_time_oct27]["bags_ready_on_time"]


def test_combined_option_not_worse_than_overtime_alone(pipeline):
    s = _summary(pipeline)
    assert s["S4_OVERTIME_AND_TRANSFER"]["bags_ready_on_time"] >= s["S2_OVERTIME"]["bags_ready_on_time"]
    assert s["S4_OVERTIME_AND_TRANSFER"]["overtime_runtime_hours"] > 0
    assert s["S4_OVERTIME_AND_TRANSFER"]["alternate_runtime_hours"] > 0


def test_mlflow_tracking_logs_every_scenario_and_sweep_point(pipeline):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from candyops.tracking import log_runs, run_records

    calls = []

    class FakeMlflow:
        def set_experiment(self, path):
            calls.append(("experiment", path))

        @contextmanager
        def start_run(self, run_name, nested=False):
            calls.append(("run", run_name, nested))
            yield SimpleNamespace(info=SimpleNamespace(run_id="parent-1"))

        def set_tags(self, tags):
            assert all(isinstance(v, str) for v in tags.values())

        def log_params(self, params):
            assert all(v is not None for v in params.values())

        def log_metrics(self, metrics):
            assert all(isinstance(v, float) for v in metrics.values())

    gold = pipeline["gold"]
    records = run_records(gold)
    assert len(records) == len(gold["gold_scenario_summary"]) + len(gold["gold_sweep"])
    assert log_runs(FakeMlflow(), records, "/Users/x/candyops-scenarios", "parent") == "parent-1"
    nested = [c for c in calls if c[0] == "run" and c[2]]
    assert len(nested) == len(records)
    assert calls[0] == ("experiment", "/Users/x/candyops-scenarios")
