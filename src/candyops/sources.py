"""Deterministic generator for the simulated source exports (bronze layer).

Four source areas, all SYNTHETIC:
  * ERP  - factories, products, materials/costs, recipes, customer orders, production orders, cost parameters
  * MES  - lines, line capability (rates/yields), line calendar, downtime events, production actuals
  * WMS/procurement - opening raw-material and finished-goods inventory, supplier purchase orders
  * QMS  - batch quality inspections (good, rejected, scrap)

Values are exported as strings, like a flat-file extract. Silver casts and validates them.
Actual production history exists only for days before the decision date (Oct 25-26).
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from .config import DECISION_DATE, HORIZON, SEED

EXTRACT_TS = "2026-10-27T05:30:00"  # export taken just before the 06:00 shift start on the breakdown day

FACTORIES = [
    # factory_id, name, region, shift_start_hour, shift_hours
    ("NFD", "Northfield Plant (fictional)", "Midwest", 6, 16),
    ("SGT", "Southgate Plant (fictional)", "South", 6, 16),
]

PRODUCTS = [
    # sku, name, pack, wholesale price per bag (modeled)
    ("SPK40", "Spooky Assortment 40ct", "40-piece Halloween assortment bag", 8.40),
    ("CHM25", "Chocolate Monster Minis 25ct", "25-piece chocolate Halloween bag", 6.20),
    ("GHO30", "Gummy Ghosts 30ct", "30-piece gummy Halloween bag", 5.10),
]

MATERIALS = [
    # material_id, name, category, uom, std cost per uom (USD)
    ("CHOC", "Milk chocolate mass", "ingredient", "kg", 6.50),
    ("GUMMY", "Gummy mass", "ingredient", "kg", 3.20),
    ("CARAMEL", "Caramel filling", "ingredient", "kg", 4.00),
    ("WRAP_SPK40", "Halloween bag film - Spooky Assortment", "seasonal_packaging", "pcs", 0.06),
    ("WRAP_CHM25", "Halloween bag film - Chocolate Monster", "seasonal_packaging", "pcs", 0.06),
    ("WRAP_GHO30", "Halloween bag film - Gummy Ghosts", "seasonal_packaging", "pcs", 0.06),
]

RECIPES = [
    # sku, material, qty per finished bag, uom
    ("SPK40", "CHOC", 0.20, "kg"),
    ("SPK40", "GUMMY", 0.15, "kg"),
    ("SPK40", "WRAP_SPK40", 1, "pcs"),
    ("CHM25", "CHOC", 0.25, "kg"),
    ("CHM25", "CARAMEL", 0.05, "kg"),
    ("CHM25", "WRAP_CHM25", 1, "pcs"),
    ("GHO30", "GUMMY", 0.30, "kg"),
    ("GHO30", "WRAP_GHO30", 1, "pcs"),
]

LINES = [
    ("NFD-A1", "NFD", "Assortment Line A1"),
    ("NFD-A2", "NFD", "Gummy Line A2"),
    ("SGT-B1", "SGT", "Assortment Line B1"),
]

CAPABILITY = [
    # line, sku, ideal rate (bags per line-hour), standard yield (good / total)
    ("NFD-A1", "SPK40", 1000, 0.97),
    ("NFD-A1", "CHM25", 1000, 0.97),
    ("NFD-A1", "GHO30", 1000, 0.97),
    ("NFD-A2", "GHO30", 800, 0.96),
    ("NFD-A2", "SPK40", 800, 0.96),
    ("SGT-B1", "SPK40", 900, 0.95),
    ("SGT-B1", "CHM25", 900, 0.95),
]

OVERTIME_LIMIT_HOURS = 4.0

# Original (pre-breakdown) production plan: line, day index (0 = Oct 25), sequence, sku, hours
PRODUCTION_PLAN = [
    ("NFD-A1", 0, 1, "SPK40", 16), ("NFD-A1", 1, 1, "CHM25", 16), ("NFD-A1", 2, 1, "SPK40", 16),
    ("NFD-A1", 3, 1, "CHM25", 16), ("NFD-A1", 4, 1, "SPK40", 8), ("NFD-A1", 4, 2, "CHM25", 8),
    ("NFD-A1", 5, 1, "CHM25", 16),
    *[("NFD-A2", d, 1, "GHO30", 16) for d in range(6)],
    ("SGT-B1", 0, 1, "SPK40", 8), ("SGT-B1", 1, 1, "CHM25", 8), ("SGT-B1", 2, 1, "SPK40", 8),
    ("SGT-B1", 3, 1, "SPK40", 8),
]

CUSTOMER_ORDERS = [
    # order_id, fictional retailer, dispatch factory, sku, bags, ready-to-ship deadline (day idx), created day idx
    ("O-1001", "Harvest Mart", "NFD", "SPK40", 15000, 2, -20),
    ("O-1002", "Moonlight Grocers", "NFD", "SPK40", 14000, 3, -19),
    ("O-1003", "Big Pumpkin Club", "NFD", "SPK40", 10000, 5, -18),
    ("O-1004", "Lantern Foods", "NFD", "CHM25", 12000, 2, -20),
    ("O-1005", "Moonlight Grocers", "NFD", "CHM25", 16000, 4, -19),
    ("O-1006", "Corner Cauldron Drug", "NFD", "CHM25", 24000, 5, -17),
    ("O-1007", "Harvest Mart", "NFD", "GHO30", 20000, 2, -20),
    ("O-1008", "Lantern Foods", "NFD", "GHO30", 30000, 4, -18),
    ("O-1009", "Big Pumpkin Club", "NFD", "GHO30", 20000, 5, -16),
    ("P-2001", "Hollow Oak Market", "SGT", "SPK40", 7000, 2, -21),
    ("P-2002", "Lantern Foods", "SGT", "CHM25", 7000, 3, -20),
    ("P-2003", "Night Owl Pharmacy", "SGT", "SPK40", 13500, 4, -18),
]

OPENING_MATERIALS = [
    # factory, material, on hand
    ("NFD", "CHOC", 14000), ("NFD", "GUMMY", 20000), ("NFD", "CARAMEL", 3200),
    ("NFD", "WRAP_SPK40", 26000), ("NFD", "WRAP_CHM25", 36000), ("NFD", "WRAP_GHO30", 50000),
    ("SGT", "CHOC", 9000), ("SGT", "GUMMY", 6000), ("SGT", "CARAMEL", 900),
    ("SGT", "WRAP_SPK40", 25000), ("SGT", "WRAP_CHM25", 8500),
]

OPENING_FINISHED_GOODS = [
    ("NFD", "SPK40", 2000), ("NFD", "CHM25", 1500), ("NFD", "GHO30", 1000),
    ("SGT", "SPK40", 1000), ("SGT", "CHM25", 600),
]

PURCHASE_ORDERS = [
    # po_id, fictional supplier, factory, material, qty, expected arrival (day idx)
    ("PO-7001", "Cocoa Ridge Supply", "NFD", "CHOC", 10000, 3),
    ("PO-7002", "Sweetfield Ingredients", "NFD", "GUMMY", 12000, 3),
    ("PO-7003", "Pumpkin Print Packaging", "NFD", "WRAP_SPK40", 16000, 2),
    ("PO-7004", "Pumpkin Print Packaging", "NFD", "WRAP_CHM25", 22000, 3),
    ("PO-7005", "Pumpkin Print Packaging", "NFD", "WRAP_GHO30", 30000, 2),
    ("PO-7006", "Cocoa Ridge Supply", "SGT", "CHOC", 4000, 3),
    ("PO-7007", "Sweetfield Ingredients", "SGT", "GUMMY", 2000, 4),
    ("PO-7008", "Pumpkin Print Packaging", "SGT", "WRAP_SPK40", 24000, 5),
    ("PO-7009", "Pumpkin Print Packaging", "SGT", "WRAP_CHM25", 12000, 5),
]

# Sensitivity check: the Southgate Halloween film POs, expedited to arrive on the decision date.
SENSITIVITY_PO_IDS = ("PO-7008", "PO-7009")

COST_PARAMETERS = [
    ("overtime_cost_per_line_hour", 450.0, "USD/line-hour",
     "Incremental crew premium + utilities for an overtime hour at the affected factory"),
    ("alternate_run_cost_per_line_hour", 220.0, "USD/line-hour",
     "Incremental crew call-in + utilities to run otherwise idle standard hours at the second factory"),
    ("transfer_cost_per_bag", 0.12, "USD/bag", "Freight + handling to move a finished bag between factories"),
    ("transfer_lead_time_days", 1.0, "days",
     "Bags shipped at end of day d are available at the destination for allocation on day d + lead time"),
    ("markdown_assumption_pct", 0.50, "fraction",
     "ASSUMPTION ONLY: post-Halloween markdown applied to leftover seasonal finished goods"),
]

BREAKDOWN = {
    "event_id": "DT-9001",
    "line_id": "NFD-A1",
    "start": "2026-10-27T06:00:00",
    "end": "2026-10-29T14:00:00",
    "reason": "Bag sealer jaw failure - estimated repair (known at decision point)",
    "event_type": "breakdown_estimate",
}


def _d(idx: int) -> str:
    return (HORIZON[0] + timedelta(days=idx)).isoformat()


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _meta(system: str, file: str) -> dict:
    return {"_source_system": system, "_source_file": file, "_extract_ts": EXTRACT_TS}


def generate_sources(seed: int = SEED) -> dict[str, list[dict]]:
    """Return {bronze_table_name: rows}. Same seed -> identical output."""
    rng = random.Random(seed)
    erp, mes, wms, qms = "SIM_ERP_EXPORT", "SIM_MES_EXPORT", "SIM_WMS_PROCUREMENT_EXPORT", "SIM_QMS_EXPORT"
    t: dict[str, list[dict]] = {}

    t["erp_factories"] = [
        {"factory_id": f, "factory_name": n, "region": r, "shift_start_hour": str(s), "shift_hours": str(h),
         **_meta(erp, "factories.csv")} for f, n, r, s, h in FACTORIES]
    t["erp_products"] = [
        {"sku_id": s, "sku_name": n, "pack_description": p, "unit_uom": "bag", "wholesale_price_usd": f"{pr:.2f}",
         "is_seasonal": "Y", **_meta(erp, "products.csv")} for s, n, p, pr in PRODUCTS]
    t["erp_materials"] = [
        {"material_id": m, "material_name": n, "category": c, "uom": u, "std_cost_usd_per_uom": f"{cost:.2f}",
         **_meta(erp, "materials.csv")} for m, n, c, u, cost in MATERIALS]
    t["erp_product_recipes"] = [
        {"sku_id": s, "material_id": m, "qty_per_bag": str(q), "uom": u, **_meta(erp, "bom.csv")}
        for s, m, q, u in RECIPES]
    t["erp_customer_orders"] = [
        {"order_id": o, "customer_name": c, "dispatch_factory_id": f, "sku_id": s, "order_qty_bags": str(q),
         "ready_to_ship_deadline": _d(dl), "order_created_ts": f"{_d(cr)}T09:{i:02d}:00",
         **_meta(erp, "sales_orders.csv")}
        for i, (o, c, f, s, q, dl, cr) in enumerate(CUSTOMER_ORDERS)]
    t["erp_production_orders"] = [
        {"production_order_id": f"PRD-{line}-{_d(d)}-{seq}", "factory_id": line.split("-")[0], "line_id": line,
         "sku_id": sku, "production_date": _d(d), "sequence": str(seq), "planned_hours": str(hrs),
         "status": "RELEASED", **_meta(erp, "production_orders.csv")}
        for line, d, seq, sku, hrs in PRODUCTION_PLAN]
    t["erp_cost_parameters"] = [
        {"parameter": p, "value": str(v), "unit": u, "description": desc, **_meta(erp, "cost_parameters.csv")}
        for p, v, u, desc in COST_PARAMETERS]

    t["mes_lines"] = [
        {"line_id": ln, "factory_id": f, "line_name": n, **_meta(mes, "lines.csv")} for ln, f, n in LINES]
    t["mes_line_capability"] = [
        {"line_id": ln, "sku_id": s, "ideal_rate_bags_per_hour": str(r), "standard_yield": str(y),
         **_meta(mes, "line_capability.csv")} for ln, s, r, y in CAPABILITY]
    t["mes_line_calendar"] = [
        {"line_id": ln, "calendar_date": day.isoformat(),
         "planned_operating_hours": "0" if day.month == 10 and day.day == 31 else "16",
         "overtime_limit_hours": "0" if day.month == 10 and day.day == 31 else str(OVERTIME_LIMIT_HOURS),
         **_meta(mes, "line_calendar.csv")}
        for ln, _, _ in LINES for day in HORIZON]

    rate = {(ln, s): (r, y) for ln, s, r, y in CAPABILITY}
    recipe_kg = {}
    for s, _m, q, u in RECIPES:
        if u == "kg":
            recipe_kg[s] = recipe_kg.get(s, 0.0) + q

    downtime_rows, actual_rows, qa_rows = [], [], []
    history_days = [i for i, day in enumerate(HORIZON) if day < DECISION_DATE]
    for line, _, _ in LINES:
        for d in history_days:
            runs = sorted([p for p in PRODUCTION_PLAN if p[0] == line and p[1] == d], key=lambda p: p[2])
            if not runs:
                continue
            stop_min = rng.randint(15, 50)
            start = datetime.fromisoformat(_d(d)) + timedelta(hours=6 + rng.randint(2, 12))
            downtime_rows.append({
                "event_id": f"DT-{len(downtime_rows) + 1:04d}", "line_id": line,
                "start_ts": _ts(start), "end_ts": _ts(start + timedelta(minutes=stop_min)),
                "reason": rng.choice(["Film splice", "Metal detector reject purge", "Weigher jam"]),
                "event_type": "minor_stop_actual", **_meta(mes, "downtime_events.csv")})
            lost = stop_min / 60.0
            batch_start = datetime.fromisoformat(_d(d)) + timedelta(hours=6)
            for i, (_, _, seq, sku, hrs) in enumerate(runs):
                # lost hours fall on the last run of the day; round first so output never exceeds runtime * rate
                run_h = round(hrs - lost if i == len(runs) - 1 else hrs, 4)
                r, y = rate[(line, sku)]
                total = int(math.floor(run_h * r + 1e-9))
                good = int(round(total * (y + rng.uniform(-0.012, 0.006))))
                reject = total - good
                batch_id = f"B-{line}-{_d(d)}-{seq}"
                actual_rows.append({
                    "batch_id": batch_id, "production_order_id": f"PRD-{line}-{_d(d)}-{seq}", "line_id": line,
                    "sku_id": sku, "production_date": _d(d), "batch_start_ts": _ts(batch_start),
                    "runtime_hours": f"{run_h:.4f}", "total_bags": str(total), **_meta(mes, "production_actuals.csv")})
                qa_rows.append({
                    "inspection_id": f"QA-{batch_id}", "batch_id": batch_id, "good_bags": str(good),
                    "rejected_bags": str(reject), "scrap_kg": f"{reject * recipe_kg[sku]:.3f}",
                    "reject_reason": "Seal integrity / underweight",
                    "inspected_ts": _ts(batch_start + timedelta(hours=run_h)),
                    **_meta(qms, "batch_inspections.csv")})
                batch_start += timedelta(hours=run_h)
    downtime_rows.append({
        "event_id": BREAKDOWN["event_id"], "line_id": BREAKDOWN["line_id"], "start_ts": BREAKDOWN["start"],
        "end_ts": BREAKDOWN["end"], "reason": BREAKDOWN["reason"], "event_type": BREAKDOWN["event_type"],
        **_meta(mes, "downtime_events.csv")})
    t["mes_downtime_events"] = downtime_rows
    t["mes_production_actuals"] = actual_rows
    t["qms_batch_inspections"] = qa_rows

    t["wms_opening_materials"] = [
        {"factory_id": f, "material_id": m, "on_hand_qty": str(q), "uom": dict((x[0], x[3]) for x in MATERIALS)[m],
         "as_of_ts": f"{_d(0)}T00:00:00", **_meta(wms, "inventory_snapshot.csv")} for f, m, q in OPENING_MATERIALS]
    t["wms_opening_finished_goods"] = [
        {"factory_id": f, "sku_id": s, "on_hand_bags": str(q), "as_of_ts": f"{_d(0)}T00:00:00",
         **_meta(wms, "fg_snapshot.csv")} for f, s, q in OPENING_FINISHED_GOODS]
    t["proc_purchase_orders"] = [
        {"po_id": p, "supplier_name": sup, "factory_id": f, "material_id": m, "order_qty": str(q),
         "uom": dict((x[0], x[3]) for x in MATERIALS)[m], "expected_arrival_date": _d(a),
         **_meta(wms, "purchase_orders.csv")} for p, sup, f, m, q, a in PURCHASE_ORDERS]
    return t
