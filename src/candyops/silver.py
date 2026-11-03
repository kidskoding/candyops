"""Bronze (string exports) -> silver (typed, conformed) normalization. Pure Python, no Spark."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .config import HORIZON

# bronze table -> (silver table, {column: type}); type in str|int|float|date|ts
SPEC: dict[str, tuple[str, dict[str, str]]] = {
    "erp_factories": ("silver_factories", {"factory_id": "str", "factory_name": "str", "region": "str",
                                           "shift_start_hour": "int", "shift_hours": "float"}),
    "erp_products": ("silver_products", {"sku_id": "str", "sku_name": "str", "pack_description": "str",
                                         "unit_uom": "str", "wholesale_price_usd": "float", "is_seasonal": "str"}),
    "erp_materials": ("silver_materials", {"material_id": "str", "material_name": "str", "category": "str",
                                           "uom": "str", "std_cost_usd_per_uom": "float"}),
    "erp_product_recipes": ("silver_recipes", {"sku_id": "str", "material_id": "str", "qty_per_bag": "float",
                                               "uom": "str"}),
    "erp_customer_orders": ("silver_customer_orders", {
        "order_id": "str", "customer_name": "str", "dispatch_factory_id": "str", "sku_id": "str",
        "order_qty_bags": "int", "ready_to_ship_deadline": "date", "order_created_ts": "ts"}),
    "erp_production_orders": ("silver_production_orders", {
        "production_order_id": "str", "factory_id": "str", "line_id": "str", "sku_id": "str",
        "production_date": "date", "sequence": "int", "planned_hours": "float", "status": "str"}),
    "erp_cost_parameters": ("silver_cost_parameters", {"parameter": "str", "value": "float", "unit": "str",
                                                       "description": "str"}),
    "mes_lines": ("silver_lines", {"line_id": "str", "factory_id": "str", "line_name": "str"}),
    "mes_line_capability": ("silver_line_capability", {"line_id": "str", "sku_id": "str",
                                                       "ideal_rate_bags_per_hour": "float", "standard_yield": "float"}),
    "mes_line_calendar": ("silver_line_calendar", {
        "line_id": "str", "calendar_date": "date", "planned_operating_hours": "float",
        "overtime_limit_hours": "float"}),
    "mes_downtime_events": ("silver_downtime_events", {"event_id": "str", "line_id": "str", "start_ts": "ts",
                                                       "end_ts": "ts", "reason": "str", "event_type": "str"}),
    "mes_production_actuals": ("silver_production_actuals", {
        "batch_id": "str", "production_order_id": "str", "line_id": "str", "sku_id": "str",
        "production_date": "date", "batch_start_ts": "ts", "runtime_hours": "float", "total_bags": "int"}),
    "qms_batch_inspections": ("silver_quality_inspections", {
        "inspection_id": "str", "batch_id": "str", "good_bags": "int", "rejected_bags": "int", "scrap_kg": "float",
        "reject_reason": "str", "inspected_ts": "ts"}),
    "wms_opening_materials": ("silver_opening_materials", {"factory_id": "str", "material_id": "str",
                                                           "on_hand_qty": "float", "uom": "str", "as_of_ts": "ts"}),
    "wms_opening_finished_goods": ("silver_opening_finished_goods", {"factory_id": "str", "sku_id": "str",
                                                                     "on_hand_bags": "int", "as_of_ts": "ts"}),
    "proc_purchase_orders": ("silver_purchase_orders", {
        "po_id": "str", "supplier_name": "str", "factory_id": "str", "material_id": "str", "order_qty": "float",
        "uom": "str", "expected_arrival_date": "date"}),
}


def _cast(value, kind: str):
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    if kind == "str":
        return str(value).strip()
    if kind == "int":
        return int(round(float(value)))
    if kind == "float":
        return float(value)
    if kind == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return date.fromisoformat(str(value)[:10])
    if kind == "ts":
        return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    raise ValueError(kind)


def daily_downtime(events: list[dict], lines: list[dict], factories: list[dict], days=HORIZON) -> list[dict]:
    """Split downtime events into hours per line per day, clipped to that factory's shift window."""
    fac_of = {ln["line_id"]: ln["factory_id"] for ln in lines}
    shift = {f["factory_id"]: (f["shift_start_hour"], f["shift_hours"]) for f in factories}
    out = {}
    for e in events:
        if e["line_id"] not in fac_of or e["start_ts"] is None or e["end_ts"] is None or e["end_ts"] <= e["start_ts"]:
            continue  # invalid events are reported by validation, never silently converted
        start_h, hours = shift[fac_of[e["line_id"]]]
        for day in days:
            w0 = datetime(day.year, day.month, day.day) + timedelta(hours=start_h)
            w1 = w0 + timedelta(hours=hours)
            overlap = (min(w1, e["end_ts"]) - max(w0, e["start_ts"])).total_seconds() / 3600.0
            if overlap > 0:
                key = (e["line_id"], day)
                row = out.setdefault(key, {"line_id": e["line_id"], "downtime_date": day, "breakdown_hours": 0.0,
                                           "minor_stop_hours": 0.0})
                col = "breakdown_hours" if e["event_type"].startswith("breakdown") else "minor_stop_hours"
                row[col] = round(row[col] + overlap, 6)
    rows = sorted(out.values(), key=lambda r: (r["line_id"], r["downtime_date"]))
    for r in rows:
        r["downtime_hours"] = round(r["breakdown_hours"] + r["minor_stop_hours"], 6)
    return rows


def normalize(bronze: dict[str, list[dict]]) -> dict[str, list[dict]]:
    silver: dict[str, list[dict]] = {}
    for btable, (stable, cols) in SPEC.items():
        rows = []
        for r in bronze.get(btable, []):
            row = {c: _cast(r.get(c), k) for c, k in cols.items()}
            row["_source_system"] = r.get("_source_system")
            rows.append(row)
        silver[stable] = rows
    for e in silver["silver_downtime_events"]:
        ok = e["start_ts"] is not None and e["end_ts"] is not None
        e["duration_hours"] = round((e["end_ts"] - e["start_ts"]).total_seconds() / 3600.0, 6) if ok else None
    silver["silver_line_daily_downtime"] = daily_downtime(
        silver["silver_downtime_events"], silver["silver_lines"], silver["silver_factories"])
    return silver
