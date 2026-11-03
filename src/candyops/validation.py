"""Data-quality checks (silver) and model-integrity checks (gold). Each check returns PASS/FAIL rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

from .config import DECISION_DATE, HALLOWEEN, HORIZON

TOL = 1e-6


def _check(results, layer, name, table, failures, detail=""):
    results.append({"layer": layer, "check_name": name, "table_name": table,
                    "status": "PASS" if not failures else "FAIL", "failed_rows": len(failures),
                    "detail": detail if not failures else "; ".join(map(str, failures[:5]))})



PRIMARY_KEYS = {
    "silver_factories": ("factory_id",), "silver_products": ("sku_id",), "silver_materials": ("material_id",),
    "silver_recipes": ("sku_id", "material_id"), "silver_customer_orders": ("order_id",),
    "silver_production_orders": ("production_order_id",), "silver_cost_parameters": ("parameter",),
    "silver_lines": ("line_id",), "silver_line_capability": ("line_id", "sku_id"),
    "silver_line_calendar": ("line_id", "calendar_date"), "silver_downtime_events": ("event_id",),
    "silver_production_actuals": ("batch_id",), "silver_quality_inspections": ("inspection_id",),
    "silver_opening_materials": ("factory_id", "material_id"),
    "silver_opening_finished_goods": ("factory_id", "sku_id"), "silver_purchase_orders": ("po_id",),
}

REQUIRED_PARAMS = ("overtime_cost_per_line_hour", "alternate_run_cost_per_line_hour", "transfer_cost_per_bag",
                   "transfer_lead_time_days", "markdown_assumption_pct")


def check_sources(s: dict[str, list[dict]]) -> list[dict]:
    res: list[dict] = []
    L = "silver"
    for t, key in PRIMARY_KEYS.items():
        rows = s.get(t, [])
        nulls = [r for r in rows if any(r.get(k) is None for k in key)]
        dupes = [k for k, n in Counter(tuple(r.get(k) for k in key) for r in rows).items() if n > 1]
        _check(res, L, "primary_key_not_null", t, nulls, f"{len(rows)} rows")
        _check(res, L, "primary_key_unique", t, dupes, f"key={key}")
        _check(res, L, "table_not_empty", t, [] if rows else ["empty"])

    fac = {r["factory_id"] for r in s["silver_factories"]}
    sku = {r["sku_id"] for r in s["silver_products"]}
    mat = {r["material_id"]: r for r in s["silver_materials"]}
    lines = {r["line_id"]: r["factory_id"] for r in s["silver_lines"]}
    cap = {(r["line_id"], r["sku_id"]) for r in s["silver_line_capability"]}
    days = set(HORIZON)

    def fk(name, table, bad):
        _check(res, L, name, table, bad)

    fk("line_factory_exists", "silver_lines", [l for l, f in lines.items() if f not in fac])
    fk("recipe_sku_exists", "silver_recipes", [r["sku_id"] for r in s["silver_recipes"] if r["sku_id"] not in sku])
    fk("recipe_material_exists", "silver_recipes",
       [r["material_id"] for r in s["silver_recipes"] if r["material_id"] not in mat])
    fk("every_sku_has_recipe", "silver_products", sorted(sku - {r["sku_id"] for r in s["silver_recipes"]}))
    fk("order_refs_exist", "silver_customer_orders",
       [r["order_id"] for r in s["silver_customer_orders"]
        if r["sku_id"] not in sku or r["dispatch_factory_id"] not in fac])
    fk("capability_refs_exist", "silver_line_capability",
       [(r["line_id"], r["sku_id"]) for r in s["silver_line_capability"]
        if r["line_id"] not in lines or r["sku_id"] not in sku])
    fk("production_order_line_sku_compatible", "silver_production_orders",
       [r["production_order_id"] for r in s["silver_production_orders"]
        if (r["line_id"], r["sku_id"]) not in cap or lines.get(r["line_id"]) != r["factory_id"]])
    fk("calendar_line_exists", "silver_line_calendar",
       [r["line_id"] for r in s["silver_line_calendar"] if r["line_id"] not in lines])
    fk("downtime_line_exists", "silver_downtime_events",
       [r["event_id"] for r in s["silver_downtime_events"] if r["line_id"] not in lines])
    fk("po_refs_exist", "silver_purchase_orders",
       [r["po_id"] for r in s["silver_purchase_orders"] if r["factory_id"] not in fac or r["material_id"] not in mat])
    fk("inventory_refs_exist", "silver_opening_materials",
       [(r["factory_id"], r["material_id"]) for r in s["silver_opening_materials"]
        if r["factory_id"] not in fac or r["material_id"] not in mat])
    fk("fg_refs_exist", "silver_opening_finished_goods",
       [(r["factory_id"], r["sku_id"]) for r in s["silver_opening_finished_goods"]
        if r["factory_id"] not in fac or r["sku_id"] not in sku])
    po_ids = {r["production_order_id"] for r in s["silver_production_orders"]}
    fk("actual_batch_has_production_order", "silver_production_actuals",
       [r["batch_id"] for r in s["silver_production_actuals"] if r["production_order_id"] not in po_ids])
    batches = {r["batch_id"]: r for r in s["silver_production_actuals"]}
    fk("inspection_has_batch", "silver_quality_inspections",
       [r["inspection_id"] for r in s["silver_quality_inspections"] if r["batch_id"] not in batches])
    inspected = {r["batch_id"] for r in s["silver_quality_inspections"]}
    fk("batch_has_inspection", "silver_production_actuals", sorted(set(batches) - inspected))

    _check(res, L, "recipe_uom_matches_material", "silver_recipes",
           [(r["sku_id"], r["material_id"]) for r in s["silver_recipes"]
            if r["material_id"] in mat and r["uom"] != mat[r["material_id"]]["uom"]])
    _check(res, L, "po_uom_matches_material", "silver_purchase_orders",
           [r["po_id"] for r in s["silver_purchase_orders"]
            if r["material_id"] in mat and r["uom"] != mat[r["material_id"]]["uom"]])
    _check(res, L, "inventory_uom_matches_material", "silver_opening_materials",
           [(r["factory_id"], r["material_id"]) for r in s["silver_opening_materials"]
            if r["material_id"] in mat and r["uom"] != mat[r["material_id"]]["uom"]])
    _check(res, L, "allowed_uoms", "silver_materials",
           [m for m, r in mat.items() if r["uom"] not in ("kg", "pcs")], "ingredients kg, wrappers pcs")
    _check(res, L, "wrappers_one_per_bag", "silver_recipes",
           [(r["sku_id"], r["material_id"]) for r in s["silver_recipes"] if r["material_id"] in mat
            and mat[r["material_id"]]["category"] == "seasonal_packaging" and r["qty_per_bag"] != 1])

    _check(res, L, "positive_quantities", "silver_customer_orders",
           [r["order_id"] for r in s["silver_customer_orders"] if not r["order_qty_bags"] or r["order_qty_bags"] <= 0])
    _check(res, L, "positive_quantities", "silver_purchase_orders",
           [r["po_id"] for r in s["silver_purchase_orders"] if not r["order_qty"] or r["order_qty"] <= 0])
    _check(res, L, "non_negative_inventory", "silver_opening_materials",
           [r for r in s["silver_opening_materials"] if r["on_hand_qty"] is None or r["on_hand_qty"] < 0])
    _check(res, L, "rate_and_yield_valid", "silver_line_capability",
           [(r["line_id"], r["sku_id"]) for r in s["silver_line_capability"]
            if not r["ideal_rate_bags_per_hour"] or r["ideal_rate_bags_per_hour"] <= 0
            or r["standard_yield"] is None or not 0 < r["standard_yield"] <= 1])
    _check(res, L, "calendar_hours_valid", "silver_line_calendar",
           [(r["line_id"], r["calendar_date"]) for r in s["silver_line_calendar"]
            if r["planned_operating_hours"] is None or r["overtime_limit_hours"] is None
            or r["planned_operating_hours"] < 0 or r["overtime_limit_hours"] < 0
            or r["planned_operating_hours"] + r["overtime_limit_hours"] > 24])
    _check(res, L, "calendar_covers_horizon", "silver_line_calendar",
           [(l, d) for l in lines for d in HORIZON
            if (l, d) not in {(r["line_id"], r["calendar_date"]) for r in s["silver_line_calendar"]}])
    sched = defaultdict(float)
    for r in s["silver_production_orders"]:
        sched[(r["line_id"], r["production_date"])] += r["planned_hours"] or 0
    planned = {(r["line_id"], r["calendar_date"]): r["planned_operating_hours"] for r in s["silver_line_calendar"]}
    _check(res, L, "schedule_within_planned_hours", "silver_production_orders",
           [k for k, h in sched.items() if h > planned.get(k, 0) + TOL])
    params = {r["parameter"] for r in s["silver_cost_parameters"]}
    _check(res, L, "required_cost_parameters_present", "silver_cost_parameters",
           [p for p in REQUIRED_PARAMS if p not in params])

    _check(res, L, "event_end_after_start", "silver_downtime_events",
           [r["event_id"] for r in s["silver_downtime_events"]
            if r["start_ts"] is None or r["end_ts"] is None or r["end_ts"] <= r["start_ts"]])
    _check(res, L, "deadline_within_halloween_window", "silver_customer_orders",
           [r["order_id"] for r in s["silver_customer_orders"]
            if r["ready_to_ship_deadline"] is None or not HORIZON[0] <= r["ready_to_ship_deadline"] < HALLOWEEN])
    _check(res, L, "order_created_before_deadline", "silver_customer_orders",
           [r["order_id"] for r in s["silver_customer_orders"]
            if r["order_created_ts"] is None or r["order_created_ts"].date() > r["ready_to_ship_deadline"]])
    _check(res, L, "dates_within_horizon", "silver_production_orders",
           [r["production_order_id"] for r in s["silver_production_orders"] if r["production_date"] not in days])
    _check(res, L, "dates_within_horizon", "silver_purchase_orders",
           [r["po_id"] for r in s["silver_purchase_orders"] if r["expected_arrival_date"] not in days])
    _check(res, L, "actuals_only_before_decision_date", "silver_production_actuals",
           [r["batch_id"] for r in s["silver_production_actuals"] if r["production_date"] >= DECISION_DATE])
    _check(res, L, "inspection_after_batch_start", "silver_quality_inspections",
           [r["inspection_id"] for r in s["silver_quality_inspections"] if r["batch_id"] in batches
            and r["inspected_ts"] < batches[r["batch_id"]]["batch_start_ts"]])

    _check(res, L, "good_plus_reject_equals_total", "silver_quality_inspections",
           [r["batch_id"] for r in s["silver_quality_inspections"] if r["batch_id"] in batches
            and r["good_bags"] + r["rejected_bags"] != batches[r["batch_id"]]["total_bags"]])
    _check(res, L, "non_negative_good_and_rejects", "silver_quality_inspections",
           [r["batch_id"] for r in s["silver_quality_inspections"] if r["good_bags"] < 0 or r["rejected_bags"] < 0])
    rate = {(r["line_id"], r["sku_id"]): r["ideal_rate_bags_per_hour"] for r in s["silver_line_capability"]}
    _check(res, L, "actual_output_within_ideal_rate", "silver_production_actuals",
           [r["batch_id"] for r in s["silver_production_actuals"]
            if r["total_bags"] > r["runtime_hours"] * rate.get((r["line_id"], r["sku_id"]), 0) + TOL])
    return res



def check_results(inputs, results) -> list[dict]:
    res: list[dict] = []
    L = "gold"
    fps = {r.start_fingerprint for r in results.values()}
    _check(res, L, "identical_start_state_at_decision_point", "all_scenarios",
           [] if len(fps) == 1 else sorted(fps), f"fingerprint={next(iter(fps)) if fps else None}")
    hist = {sid: sorted((p["run_id"], p["total_bags"], p["good_bags"]) for p in r.logs.production
                        if p["phase"] == "actual") for sid, r in results.items()}
    _check(res, L, "identical_pre_breakdown_actuals", "gold_daily_line_production",
           [] if len({repr(v) for v in hist.values()}) <= 1 else list(hist))
    for sid, r in results.items():
        for po_id, new_date in r.scenario.po_arrival_override:
            _check(res, L, "sensitivity_override_not_before_decision", sid,
                   [] if new_date >= inputs.decision_date else [po_id])

        mb = [m for m in r.logs.materials
              if abs(m["opening_qty"] + m["receipts_qty"] - m["consumed_qty"] - m["closing_qty"]) > 1e-3]
        neg = [(m["date"], m["factory_id"], m["material_id"]) for m in r.logs.materials if m["closing_qty"] < -1e-6]
        _check(res, L, "material_balance_conserved", sid, mb)
        _check(res, L, "material_never_negative", sid, neg)
        fb = [f for f in r.logs.finished_goods
              if f["opening_bags"] + f["transfer_in_bags"] + f["produced_to_stock_bags"] - f["allocated_bags"]
              != f["closing_bags"]]
        _check(res, L, "finished_goods_balance_conserved", sid, fb)
        _check(res, L, "finished_goods_never_negative", sid,
               [(f["date"], f["factory_id"], f["sku_id"]) for f in r.logs.finished_goods if f["closing_bags"] < 0])
        prod = r.logs.production
        _check(res, L, "good_plus_reject_equals_total", sid,
               [p["run_id"] for p in prod if p["good_bags"] + p["reject_bags"] != p["total_bags"]
                or p["reject_bags"] < 0])
        cons = defaultdict(float)
        for p in prod:
            for m, q in inputs.recipes[p["sku_id"]].items():
                cons[(p["date"], p["factory_id"], m)] += p["total_bags"] * q
        logged = {(m["date"], m["factory_id"], m["material_id"]): m["consumed_qty"] for m in r.logs.materials}
        _check(res, L, "materials_consumed_for_total_output_incl_rejects", sid,
               [k for k, v in cons.items() if abs(v - logged.get(k, 0.0)) > 1e-3])
        cap = [(d["date"], d["line_id"]) for d in r.logs.line_days if d["phase"] == "simulated" and (
            d["runtime_standard_hours"] > d["standard_hours_available"] + TOL
            or d["runtime_overtime_hours"] > d["overtime_hours_available"] + TOL
            or d["runtime_hours"] > 24 + TOL)]
        _check(res, L, "line_capacity_respected", sid, cap)
        alloc = defaultdict(int)
        late = []
        orders = {o.order_id: o for o in inputs.orders}
        for a in r.logs.allocations:
            alloc[a["order_id"]] += a["allocated_bags"]
            o = orders[a["order_id"]]
            if a["date"] > o.deadline or a["factory_id"] != o.factory_id or a["sku_id"] != o.sku_id:
                late.append(a["order_id"])
        _check(res, L, "no_over_allocation", sid, [k for k, v in alloc.items() if v > orders[k].qty])
        _check(res, L, "allocation_only_by_deadline_at_dispatch_factory", sid, late)
        _check(res, L, "remaining_matches_allocations", sid,
               [k for k, o in orders.items() if o.qty - alloc[k] != r.final_state.remaining[k]])
        lead = int(round(inputs.params.get("transfer_lead_time_days", 1)))
        _check(res, L, "transfer_lead_time_applied", sid,
               [t["run_id"] for t in r.logs.transfers if t["arrival_date"] != t["ship_date"] + timedelta(days=lead)])
        shipped = sum(t["bags"] for t in r.logs.transfers)
        arrived = sum(f["transfer_in_bags"] for f in r.logs.finished_goods)
        transit = sum(t["qty"] for t in r.final_state.in_transit)
        _check(res, L, "transfers_conserved", sid, [] if shipped == arrived + transit else [(shipped, arrived, transit)])
        produced = defaultdict(int)
        for p in prod:
            produced[(p["factory_id"] if not p["ship_to"] else p["ship_to"], p["sku_id"])] += p["good_bags"]
        fg_end = defaultdict(int)
        for t in r.final_state.in_transit:
            fg_end[(t["to"], t["sku_id"])] += t["qty"]
        for k, v in r.final_state.fg.items():
            fg_end[k] += v
        alloc_fs = defaultdict(int)
        for a in r.logs.allocations:
            alloc_fs[(a["factory_id"], a["sku_id"])] += a["allocated_bags"]
        keys = set(produced) | set(fg_end) | set(alloc_fs) | set(inputs.opening_fg)
        _check(res, L, "finished_goods_conserved_over_horizon", sid,
               [k for k in keys if inputs.opening_fg.get(k, 0) + produced[k] != alloc_fs[k] + fg_end[k]])
        if r.scenario.recovery:
            starved = [p["run_id"] for p in prod if p["run_type"] == "baseline"
                       and p["limiting_factor"].startswith("material")]
            _check(res, L, "recovery_does_not_starve_baseline", sid, starved)
    return res
