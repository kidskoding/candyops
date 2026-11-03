"""Gold-layer tables derived from scenario results. Every number here is a modeled output on synthetic data."""

from __future__ import annotations

from collections import defaultdict

from .model import Inputs
from .simulation import ScenarioResult

REFERENCE = "S0_REFERENCE_NO_BREAKDOWN"
BASE_OPTION = "S1_NO_RECOVERY"


def ratio(num: float, den: float) -> float | None:
    """Zero-safe ratio: returns None (shown as N/A) instead of dividing by zero."""
    return None if not den else round(num / den, 6)


def std_cost_per_bag(inputs: Inputs, sku: str) -> float:
    return sum(q * inputs.materials[m]["std_cost_usd_per_uom"] for m, q in inputs.recipes[sku].items())


def order_fulfillment(inputs: Inputs, results: dict[str, ScenarioResult]) -> list[dict]:
    ref = results.get(REFERENCE)
    base = results.get(BASE_OPTION)
    rows = []
    for sid, r in results.items():
        last_alloc = {}
        for a in r.logs.allocations:
            last_alloc[a["order_id"]] = max(last_alloc.get(a["order_id"], a["date"]), a["date"])
        for o in sorted(inputs.orders, key=lambda o: o.order_id):
            ready = o.qty - r.final_state.remaining[o.order_id]
            ref_full = ref is not None and ref.final_state.remaining[o.order_id] == 0
            base_full = base is not None and base.final_state.remaining[o.order_id] == 0
            rows.append({
                "scenario_id": sid, "order_id": o.order_id, "customer_name": o.customer,
                "dispatch_factory_id": o.factory_id, "sku_id": o.sku_id, "order_qty_bags": o.qty,
                "ready_to_ship_deadline": o.deadline, "ready_on_time_bags": ready,
                "short_bags": o.qty - ready, "fully_ready_on_time": ready == o.qty,
                "ready_on_time_pct": ratio(ready, o.qty), "last_allocation_date": last_alloc.get(o.order_id),
                "status": "READY" if ready == o.qty else ("PARTIAL" if ready > 0 else "NOT READY"),
                "at_risk_after_breakdown": ref_full and not base_full,
                "short_value_usd": round((o.qty - ready) * inputs.products[o.sku_id]["wholesale_price_usd"], 2)})
    return rows


def seasonal_exposure(inputs: Inputs, results: dict[str, ScenarioResult]) -> list[dict]:
    mk = inputs.params.get("markdown_assumption_pct", 0.0)
    rows = []
    for sid, r in results.items():
        transit = defaultdict(int)
        for t in r.final_state.in_transit:
            transit[(t["to"], t["sku_id"])] += t["qty"]
        for (f, sku) in sorted(set(r.final_state.fg) | set(transit)):
            bags = r.final_state.fg.get((f, sku), 0) + transit[(f, sku)]
            price = inputs.products[sku]["wholesale_price_usd"]
            rows.append({"scenario_id": sid, "item_type": "finished_goods", "factory_id": f, "item_id": sku,
                         "uom": "bag", "remaining_qty": bags, "in_transit_qty": transit[(f, sku)],
                         "std_cost_value_usd": round(bags * std_cost_per_bag(inputs, sku), 2),
                         "wholesale_value_usd": round(bags * price, 2),
                         "assumed_markdown_usd": round(bags * price * mk, 2)})
        for (f, m), q in sorted(r.final_state.raw.items()):
            if inputs.materials[m]["category"] == "seasonal_packaging":
                rows.append({"scenario_id": sid, "item_type": "seasonal_packaging", "factory_id": f, "item_id": m,
                             "uom": inputs.materials[m]["uom"], "remaining_qty": round(q, 3), "in_transit_qty": 0,
                             "std_cost_value_usd": round(q * inputs.materials[m]["std_cost_usd_per_uom"], 2),
                             "wholesale_value_usd": None, "assumed_markdown_usd": None})
    return rows


def recovery_capacity(results: dict[str, ScenarioResult]) -> list[dict]:
    """Where spare line-hours did or did not become usable output."""
    rows = []
    for sid, r in results.items():
        exec_rows = [p for p in r.logs.production if p["run_type"] in ("overtime", "transfer")]
        for s in r.slots:
            runs = [p for p in exec_rows if p["line_id"] == s["line_id"] and p["date"] == s["date"]]
            runtime = sum(p["runtime_hours"] for p in runs)
            blocked = sum(p["available_hours"] - p["runtime_hours"] for p in runs
                          if p["limiting_factor"].startswith("material"))
            mats = sorted({p["limiting_factor"].split(":", 1)[1] for p in runs
                           if p["limiting_factor"].startswith("material")})
            unused = max(0.0, s["capacity_hours"] - s["planned_hours"])
            if s["line_down_full_day"]:
                status = "unavailable: line down all day"
            elif s["capacity_hours"] <= 0:
                status = "no spare hours"
            elif not s["timing_eligible"]:
                status = "unusable: output would arrive after every deadline"
            elif blocked > 1e-6 and runtime < 1e-6:
                status = "blocked: " + ", ".join(mats)
            elif blocked > 1e-6:
                status = "partly blocked: " + ", ".join(mats)
            elif s["planned_hours"] > 0:
                status = "used"
            else:
                status = "unused: no remaining compatible demand"
            rows.append({"scenario_id": sid, "date": s["date"], "factory_id": s["factory_id"],
                         "line_id": s["line_id"], "mode": s["mode"], "spare_hours": round(s["capacity_hours"], 4),
                         "recovery_hours_planned": round(s["planned_hours"], 4),
                         "recovery_runtime_hours": round(runtime, 4),
                         "material_blocked_hours": round(blocked, 4), "unused_hours": round(unused, 4),
                         "timing_eligible": s["timing_eligible"], "status": status})
    return rows


def constraint_diagnostics(inputs: Inputs, results: dict[str, ScenarioResult]) -> tuple[list[dict], dict]:
    rows, primary = [], {}
    affected = {o.order_id for o in inputs.orders if o.factory_id == inputs.affected_factory}
    for sid, r in results.items():
        post = [p for p in r.logs.production if p["phase"] == "simulated"]
        equip = sum(p["lost_equipment_bags"] for p in post if p["run_type"] == "baseline")
        mat = defaultdict(int)
        for p in post:
            if p["run_type"] in ("overtime", "transfer") and p["lost_material_bags"]:
                mat[p["limiting_factor"].split(":", 1)[1]] += p["lost_material_bags"]
        unplaced = sum(v for k, v in r.plan_remaining.items() if k in affected)
        short = sum(v for k, v in r.final_state.remaining.items() if k in affected)
        rows.append({"scenario_id": sid, "constraint": "equipment", "item": "baseline hours lost to breakdown",
                     "bags": equip, "basis": "planned total bags not producible"})
        for m, v in sorted(mat.items()):
            rows.append({"scenario_id": sid, "constraint": inputs.materials[m]["category"], "item": m, "bags": v,
                         "basis": "recovery total bags blocked by material"})
        if r.scenario.recovery:
            rows.append({"scenario_id": sid, "constraint": "timing/capacity",
                         "item": "shortfall with no time-feasible recovery hours", "bags": unplaced,
                         "basis": "planner's projected unmet bags after scheduling all feasible hours"})
        by_cat = defaultdict(int)
        for m, v in mat.items():
            by_cat[inputs.materials[m]["category"]] += v
        if short == 0:
            label, detail = "none", "all affected-factory orders ready on time"
        elif not r.scenario.recovery:
            label = "equipment" if r.scenario.include_breakdown else "none"
            detail = f"{equip} planned bags lost to the {inputs.affected_line} breakdown; no recovery applied"
        else:
            cands = {f"material:{c}": v for c, v in by_cat.items()}
            cands["timing/capacity"] = unplaced
            label = max(sorted(cands), key=lambda k: cands[k])
            top = ", ".join(f"{m} {v}" for m, v in sorted(mat.items(), key=lambda kv: -kv[1])) or "none"
            detail = (f"recovery bags blocked by materials: {top}; "
                      f"shortfall with no time-feasible recovery hours: {unplaced}")
        primary[sid] = (label, detail)
    return rows, primary


def scenario_summary(inputs: Inputs, results: dict[str, ScenarioResult], orders: list[dict],
                     exposure: list[dict], primary: dict) -> list[dict]:
    p = inputs.params
    rows = []
    base_ready = sum(o["ready_on_time_bags"] for o in orders if o["scenario_id"] == BASE_OPTION)
    for sid, r in results.items():
        so = [o for o in orders if o["scenario_id"] == sid]
        prod = r.logs.production
        ot_h = sum(x["runtime_hours"] for x in prod if x["run_type"] == "overtime")
        alt_h = sum(x["runtime_hours"] for x in prod if x["run_type"] == "transfer")
        shipped = sum(t["bags"] for t in r.logs.transfers)
        ot_cost = ot_h * p.get("overtime_cost_per_line_hour", 0.0)
        alt_cost = alt_h * p.get("alternate_run_cost_per_line_hour", 0.0)
        freight = shipped * p.get("transfer_cost_per_bag", 0.0)
        incr = ot_cost + alt_cost + freight
        ready = sum(o["ready_on_time_bags"] for o in so)
        ordered = sum(o["order_qty_bags"] for o in so)
        aff = [o for o in so if o["dispatch_factory_id"] == inputs.affected_factory]
        good = sum(x["good_bags"] for x in prod)
        total = sum(x["total_bags"] for x in prod)
        ld = r.logs.line_days
        fg_exp = [e for e in exposure if e["scenario_id"] == sid and e["item_type"] == "finished_goods"]
        wrap_exp = [e for e in exposure if e["scenario_id"] == sid and e["item_type"] == "seasonal_packaging"]
        label, detail = primary[sid]
        rows.append({
            "scenario_id": sid, "scenario_name": r.scenario.name, "scenario_kind": r.scenario.kind,
            "description": r.scenario.description, "start_state_fingerprint": r.start_fingerprint,
            "orders_total": len(so), "orders_fully_ready": sum(o["fully_ready_on_time"] for o in so),
            "orders_short": sum(not o["fully_ready_on_time"] for o in so),
            "bags_ordered": ordered, "bags_ready_on_time": ready, "bags_short": ordered - ready,
            "on_time_ready_rate_bags": ratio(ready, ordered),
            "on_time_ready_rate_orders": ratio(sum(o["fully_ready_on_time"] for o in so), len(so)),
            "affected_factory_ready_rate_bags": ratio(sum(o["ready_on_time_bags"] for o in aff),
                                                      sum(o["order_qty_bags"] for o in aff)),
            "short_value_usd": round(sum(o["short_value_usd"] for o in so), 2),
            "recovery_hours_planned": round(sum(x.hours for x in r.recovery_runs), 4),
            "overtime_runtime_hours": round(ot_h, 4), "alternate_runtime_hours": round(alt_h, 4),
            "transfer_bags_shipped": shipped, "overtime_cost_usd": round(ot_cost, 2),
            "alternate_run_cost_usd": round(alt_cost, 2), "transfer_freight_usd": round(freight, 2),
            "incremental_cost_usd": round(incr, 2),
            "incremental_ready_bags_vs_s1": ready - base_ready,
            "cost_per_incremental_ready_bag_usd": (ratio(incr, ready - base_ready)
                                                   if r.scenario.recovery and ready > base_ready else None),
            "total_bags_produced": total, "good_bags": good, "reject_bags": total - good,
            "quality_yield": ratio(good, total),
            "scrap_kg": round(sum(x["scrap_kg"] for x in prod), 3),
            "planned_operating_hours": round(sum(x["planned_operating_hours"] for x in ld), 4),
            "downtime_hours": round(sum(x["downtime_hours"] for x in ld), 4),
            "runtime_hours": round(sum(x["runtime_hours"] for x in ld), 4),
            # availability = standard runtime / scheduled standard hours (unscheduled idle time excluded)
            "availability": ratio(sum(x["runtime_standard_hours"] for x in ld),
                                  sum(x["scheduled_standard_hours"] for x in ld)),
            "scheduled_hours": round(sum(x["scheduled_standard_hours"] + x["scheduled_overtime_hours"] for x in ld), 4),
            "seasonal_fg_remaining_bags": sum(e["remaining_qty"] for e in fg_exp),
            "seasonal_fg_std_cost_usd": round(sum(e["std_cost_value_usd"] for e in fg_exp), 2),
            "seasonal_fg_assumed_markdown_usd": round(sum(e["assumed_markdown_usd"] for e in fg_exp), 2),
            "seasonal_wrappers_remaining_pcs": round(sum(e["remaining_qty"] for e in wrap_exp), 3),
            "primary_constraint": label, "constraint_detail": detail})
    return rows


def sensitivity(summary: list[dict], base="S3_TRANSFER", test="S3B_TRANSFER_EARLY_WRAPPERS") -> list[dict]:
    by = {s["scenario_id"]: s for s in summary}
    if base not in by or test not in by:
        return []
    b, t = by[base], by[test]
    delta = t["bags_ready_on_time"] - b["bags_ready_on_time"]
    verdict = ("Removing the Southgate wrapper constraint increased on-time ready bags: wrappers were binding in S3."
               if delta > 0 else
               "Earlier wrappers did not change on-time ready bags: wrappers were not the binding constraint in S3.")
    return [{"base_scenario_id": base, "test_scenario_id": test,
             "change_tested": "Southgate Halloween film POs arrive Oct 27 instead of Oct 30",
             "base_bags_ready_on_time": b["bags_ready_on_time"], "test_bags_ready_on_time": t["bags_ready_on_time"],
             "delta_bags_ready_on_time": delta,
             "base_orders_fully_ready": b["orders_fully_ready"], "test_orders_fully_ready": t["orders_fully_ready"],
             "base_incremental_cost_usd": b["incremental_cost_usd"],
             "test_incremental_cost_usd": t["incremental_cost_usd"],
             "test_primary_constraint": t["primary_constraint"], "test_constraint_detail": t["constraint_detail"],
             "verdict": verdict}]


def gold_tables(inputs: Inputs, results: dict[str, ScenarioResult]) -> dict[str, list[dict]]:
    orders = order_fulfillment(inputs, results)
    exposure = seasonal_exposure(inputs, results)
    diag, primary = constraint_diagnostics(inputs, results)
    summary = scenario_summary(inputs, results, orders, exposure, primary)

    def cat(name):
        return [row for r in results.values() for row in getattr(r.logs, name)]

    recovery_runs = [{"scenario_id": sid, "run_id": x.run_id, "date": x.date, "factory_id": x.factory_id,
                      "line_id": x.line_id, "sku_id": x.sku_id, "hours": x.hours, "run_type": x.run_type,
                      "ship_to": x.ship_to} for sid, r in results.items() for x in r.recovery_runs]
    return {
        "gold_daily_line_production": cat("production"),
        "gold_daily_line_capacity": cat("line_days"),
        "gold_material_balance": cat("materials"),
        "gold_finished_goods_balance": cat("finished_goods"),
        "gold_order_allocations": cat("allocations"),
        "gold_transfers": cat("transfers"),
        "gold_recovery_plan": recovery_runs,
        "gold_order_fulfillment": orders,
        "gold_seasonal_exposure": exposure,
        "gold_recovery_capacity": recovery_capacity(results),
        "gold_constraint_diagnostics": diag,
        "gold_scenario_summary": summary,
        "gold_sensitivity": sensitivity(summary),
    }
