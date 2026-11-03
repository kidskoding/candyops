"""Typed model inputs built from silver rows (works for local rows or rows collected from Spark)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from .config import DECISION_DATE, HORIZON


@dataclass(frozen=True)
class Order:
    order_id: str
    customer: str
    factory_id: str  # dispatch factory: the only place this order can be made ready to ship
    sku_id: str
    qty: int
    deadline: date  # ready-to-ship by end of this day
    created: datetime


@dataclass(frozen=True)
class Run:
    run_id: str
    date: date
    factory_id: str
    line_id: str
    sku_id: str
    hours: float
    run_type: str = "baseline"  # baseline | overtime | transfer
    seq: int = 0
    ship_to: str | None = None  # transfer runs ship their good output to this factory


@dataclass
class Inputs:
    days: list[date]
    decision_date: date
    factories: dict[str, dict]
    lines: dict[str, str]  # line -> factory
    capability: dict[tuple[str, str], tuple[float, float]]  # (line, sku) -> (rate bags/h, yield)
    calendar: dict[tuple[str, date], tuple[float, float]]  # (line, day) -> (planned hours, overtime limit)
    downtime_minor: dict[tuple[str, date], float]
    downtime_breakdown: dict[tuple[str, date], float]
    recipes: dict[str, dict[str, float]]
    materials: dict[str, dict]
    products: dict[str, dict]
    opening_raw: dict[tuple[str, str], float]
    opening_fg: dict[tuple[str, str], int]
    purchase_orders: list[dict]
    orders: list[Order]
    plan_runs: list[Run]
    actuals: list[dict]
    params: dict[str, float]
    affected_line: str | None = None
    affected_factory: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def forward_days(self) -> list[date]:
        return [d for d in self.days if d >= self.decision_date]

    @property
    def history_days(self) -> list[date]:
        return [d for d in self.days if d < self.decision_date]


def build_inputs(silver: dict[str, list[dict]], days=HORIZON, decision_date=DECISION_DATE) -> Inputs:
    """Row order is irrelevant (Spark collect() order is not guaranteed): every list is sorted by its key."""
    silver = {t: sorted(rows, key=lambda r: repr(sorted((k, repr(v)) for k, v in r.items())))
              for t, rows in silver.items()}
    lines = {r["line_id"]: r["factory_id"] for r in silver["silver_lines"]}
    breakdown, minor = {}, {}
    for r in silver["silver_line_daily_downtime"]:
        if r["breakdown_hours"]:
            breakdown[(r["line_id"], r["downtime_date"])] = float(r["breakdown_hours"])
        if r["minor_stop_hours"]:
            minor[(r["line_id"], r["downtime_date"])] = float(r["minor_stop_hours"])
    affected = sorted({l for (l, _d) in breakdown})
    recipes: dict[str, dict[str, float]] = {}
    for r in silver["silver_recipes"]:
        recipes.setdefault(r["sku_id"], {})[r["material_id"]] = float(r["qty_per_bag"])
    planned_hours = {r["production_order_id"]: float(r["planned_hours"]) for r in silver["silver_production_orders"]}
    qa = {r["batch_id"]: r for r in silver["silver_quality_inspections"]}
    actuals = []
    for a in silver["silver_production_actuals"]:
        q = qa.get(a["batch_id"], {})
        actuals.append({
            "batch_id": a["batch_id"], "production_order_id": a["production_order_id"], "date": a["production_date"],
            "line_id": a["line_id"], "factory_id": lines.get(a["line_id"]), "sku_id": a["sku_id"],
            "planned_hours": planned_hours.get(a["production_order_id"], 0.0),
            "runtime_hours": float(a["runtime_hours"]), "total": int(a["total_bags"]),
            "good": int(q.get("good_bags", 0)), "reject": int(q.get("rejected_bags", 0)),
            "scrap_kg": float(q.get("scrap_kg", 0.0))})
    return Inputs(
        days=list(days),
        decision_date=decision_date,
        factories={r["factory_id"]: r for r in silver["silver_factories"]},
        lines=lines,
        capability={(r["line_id"], r["sku_id"]): (float(r["ideal_rate_bags_per_hour"]), float(r["standard_yield"]))
                    for r in silver["silver_line_capability"]},
        calendar={(r["line_id"], r["calendar_date"]): (float(r["planned_operating_hours"]),
                                                        float(r["overtime_limit_hours"]))
                  for r in silver["silver_line_calendar"]},
        downtime_minor=minor,
        downtime_breakdown=breakdown,
        recipes=recipes,
        materials={r["material_id"]: r for r in silver["silver_materials"]},
        products={r["sku_id"]: r for r in silver["silver_products"]},
        opening_raw={(r["factory_id"], r["material_id"]): float(r["on_hand_qty"])
                     for r in silver["silver_opening_materials"]},
        opening_fg={(r["factory_id"], r["sku_id"]): int(r["on_hand_bags"])
                    for r in silver["silver_opening_finished_goods"]},
        purchase_orders=[{"po_id": r["po_id"], "factory_id": r["factory_id"], "material_id": r["material_id"],
                          "qty": float(r["order_qty"]), "arrival_date": r["expected_arrival_date"],
                          "supplier_name": r["supplier_name"]} for r in silver["silver_purchase_orders"]],
        orders=[Order(r["order_id"], r["customer_name"], r["dispatch_factory_id"], r["sku_id"],
                      int(r["order_qty_bags"]), r["ready_to_ship_deadline"], r["order_created_ts"])
                for r in silver["silver_customer_orders"]],
        plan_runs=[Run(r["production_order_id"], r["production_date"], r["factory_id"], r["line_id"], r["sku_id"],
                       float(r["planned_hours"]), "baseline", int(r["sequence"]))
                   for r in silver["silver_production_orders"]],
        actuals=actuals,
        params={r["parameter"]: float(r["value"]) for r in silver["silver_cost_parameters"]},
        affected_line=affected[0] if affected else None,
        affected_factory=lines.get(affected[0]) if affected else None,
    )
