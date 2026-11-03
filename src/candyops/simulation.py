"""Transparent, rule-based daily simulation of the Halloween recovery problem. Pure Python.

Daily event sequence (applied identically to every day and scenario):
  1. Supplier purchase orders due today are received into raw-material stock (start of day).
  2. Inter-factory transfers due today arrive into the destination's finished-goods stock.
  3. Production runs execute in order: baseline -> overtime -> transfer, then line, then sequence.
     * Baseline and transfer runs draw on the line's standard hours (planned operating hours - downtime);
       overtime runs draw on overtime hours, which exist only if the line is not down the whole standard day.
     * When downtime reduces a line's hours, the last runs in the day's sequence lose hours.
     * Each run consumes materials for TOTAL output (good + rejects); good = floor(total * yield).
     * Recovery runs may not use material reserved for the factory's remaining baseline runs.
  4. Good output goes to the producing factory's finished goods, or (transfer runs) ships at end of day and
     arrives at the dispatch factory on day + lead time.
  5. End of day: each factory allocates its finished goods to its own open orders whose ready-to-ship
     deadline is today or later, earliest deadline first (ties: order created time, then order id).
     Partial allocation is allowed. Nothing is allocated after an order's deadline.
Cutoff convention: an order with deadline D is ready to ship on time if allocated by the end of day D.
"""

from __future__ import annotations

import copy
import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from .model import Inputs, Run
from .sources import SENSITIVITY_PO_IDS

EPS = 1e-9
RUN_ORDER = {"actual": 0, "baseline": 0, "overtime": 1, "transfer": 2}
HOUR_STEP = 0.25


def floor_units(x: float) -> int:
    return int(math.floor(x + EPS))


@dataclass
class State:
    raw: dict  # (factory, material) -> qty
    fg: dict  # (factory, sku) -> bags
    remaining: dict  # order_id -> bags still to be made ready
    in_transit: list = field(default_factory=list)

    def fingerprint(self) -> str:
        payload = repr((sorted((k, round(v, 6)) for k, v in self.raw.items()),
                        sorted(self.fg.items()), sorted(self.remaining.items()),
                        sorted((t["sku_id"], t["qty"], t["from"], t["to"], str(t["arrival_date"]))
                               for t in self.in_transit)))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class Logs:
    production: list = field(default_factory=list)
    line_days: list = field(default_factory=list)
    materials: list = field(default_factory=list)
    finished_goods: list = field(default_factory=list)
    allocations: list = field(default_factory=list)
    transfers: list = field(default_factory=list)

    def tables(self):
        return {"production": self.production, "line_days": self.line_days, "materials": self.materials,
                "finished_goods": self.finished_goods, "allocations": self.allocations,
                "transfers": self.transfers}


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    name: str
    description: str
    kind: str  # reference | option | sensitivity
    recovery: str | None = None  # None | overtime | transfer
    include_breakdown: bool = True
    po_arrival_override: tuple = ()  # ((po_id, new_date), ...)


@dataclass
class ScenarioResult:
    scenario: Scenario
    logs: Logs
    final_state: State
    start_fingerprint: str
    recovery_runs: list
    slots: list
    downtime: dict
    plan_remaining: dict  # planner's capacity-only projection of unmet bags per order (decision-time view)


def default_scenarios(decision_date: date) -> list[Scenario]:
    return [
        Scenario("S0_REFERENCE_NO_BREAKDOWN", "Reference: original plan, no breakdown",
                 "Counterfactual used only to identify which orders the breakdown puts at risk. Not an option.",
                 "reference", None, include_breakdown=False),
        Scenario("S1_NO_RECOVERY", "Disrupted schedule, no recovery",
                 "Original schedule minus the breakdown hours; accept the shortfall.", "option"),
        Scenario("S2_OVERTIME", "Limited overtime at Northfield",
                 "Add overtime (max 4 h per line-day) on Northfield lines that are not down.", "option", "overtime"),
        Scenario("S3_TRANSFER", "Move eligible production to Southgate",
                 "Use Southgate's idle standard hours for compatible SKUs and truck good bags to Northfield.",
                 "option", "transfer"),
        Scenario("S3B_TRANSFER_EARLY_WRAPPERS", "Sensitivity: S3 with Southgate film delivered Oct 27",
                 "Same as S3, but Southgate's Halloween film purchase orders arrive on the decision date.",
                 "sensitivity", "transfer", po_arrival_override=tuple((p, decision_date) for p in SENSITIVITY_PO_IDS)),
    ]



def new_state(inputs: Inputs) -> State:
    return State(raw=dict(inputs.opening_raw), fg=dict(inputs.opening_fg),
                 remaining={o.order_id: o.qty for o in inputs.orders}, in_transit=[])


def line_windows(inputs: Inputs, day: date, downtime: dict) -> dict:
    out = {}
    for line in sorted(inputs.lines):
        planned, ot_limit = inputs.calendar.get((line, day), (0.0, 0.0))
        dt = min(downtime.get((line, day), 0.0), planned)
        out[line] = {"planned": planned, "downtime": dt, "std": planned - dt,
                     "ot": ot_limit if (planned > 0 and dt < planned - EPS) else 0.0}
    return out


def _material_keys(inputs: Inputs, state: State):
    keys = set(inputs.opening_raw) | {(p["factory_id"], p["material_id"]) for p in inputs.purchase_orders}
    return sorted(keys | set(state.raw))


def _fg_keys(inputs: Inputs, state: State):
    keys = set(inputs.opening_fg) | {(o.factory_id, o.sku_id) for o in inputs.orders}
    keys |= {(inputs.lines[l], s) for (l, s) in inputs.capability}
    return sorted(keys | set(state.fg))


def _allocate(state: State, inputs: Inputs, day: date, scenario_id: str, logs: Logs) -> dict:
    allocated = defaultdict(int)
    for f in sorted(inputs.factories):
        open_orders = sorted((o for o in inputs.orders
                              if o.factory_id == f and o.deadline >= day and state.remaining[o.order_id] > 0),
                             key=lambda o: (o.deadline, o.created, o.order_id))
        for o in open_orders:
            q = min(state.remaining[o.order_id], state.fg.get((f, o.sku_id), 0))
            if q > 0:
                state.fg[(f, o.sku_id)] -= q
                state.remaining[o.order_id] -= q
                allocated[(f, o.sku_id)] += q
                logs.allocations.append({"scenario_id": scenario_id, "date": day, "factory_id": f,
                                         "order_id": o.order_id, "sku_id": o.sku_id, "allocated_bags": q,
                                         "deadline": o.deadline})
    return allocated


def step_day(state: State, inputs: Inputs, day: date, runs: list, downtime: dict, scenario_id: str, logs: Logs,
             *, enforce_materials: bool = True, reserve=None, actuals: list | None = None) -> None:
    open_raw = {k: state.raw.get(k, 0.0) for k in _material_keys(inputs, state)}
    open_fg = {k: state.fg.get(k, 0) for k in _fg_keys(inputs, state)}
    phase = "actual" if actuals is not None else "simulated"

    # 1. supplier receipts
    receipts = defaultdict(float)
    for po in inputs.purchase_orders:
        if po["arrival_date"] == day:
            k = (po["factory_id"], po["material_id"])
            state.raw[k] = state.raw.get(k, 0.0) + po["qty"]
            receipts[k] += po["qty"]
    # 2. transfer arrivals
    transfer_in = defaultdict(int)
    for t in [t for t in state.in_transit if t["arrival_date"] == day]:
        state.fg[(t["to"], t["sku_id"])] = state.fg.get((t["to"], t["sku_id"]), 0) + t["qty"]
        transfer_in[(t["to"], t["sku_id"])] += t["qty"]
        state.in_transit.remove(t)

    # 3. production
    windows = line_windows(inputs, day, downtime)
    left = {l: {"std": w["std"], "ot": w["ot"]} for l, w in windows.items()}
    sched = defaultdict(float)
    runtime = defaultdict(float)
    consumed, shortfall = defaultdict(float), defaultdict(float)
    to_stock, shipped = defaultdict(int), defaultdict(int)

    def consume(f, sku, qty):
        for m, per in inputs.recipes[sku].items():
            use = round(qty * per, 6)
            state.raw[(f, m)] = round(state.raw.get((f, m), 0.0) - use, 6)
            consumed[(f, m)] += use

    def scrap_kg(sku, rejects):
        return round(rejects * sum(q for m, q in inputs.recipes[sku].items()
                                   if inputs.materials[m]["uom"] == "kg"), 3)

    if actuals is not None:
        for a in sorted(actuals, key=lambda a: a["batch_id"]):
            f = inputs.lines[a["line_id"]]
            consume(f, a["sku_id"], a["total"])
            state.fg[(f, a["sku_id"])] = state.fg.get((f, a["sku_id"]), 0) + a["good"]
            to_stock[(f, a["sku_id"])] += a["good"]
            sched[(a["line_id"], "std")] += a["planned_hours"]
            runtime[(a["line_id"], "std")] += a["runtime_hours"]
            rate, _y = inputs.capability[(a["line_id"], a["sku_id"])]
            logs.production.append({
                "scenario_id": scenario_id, "date": day, "phase": phase, "factory_id": f, "line_id": a["line_id"],
                "sku_id": a["sku_id"], "run_id": a["production_order_id"], "run_type": "actual", "ship_to": None,
                "planned_hours": a["planned_hours"], "available_hours": a["runtime_hours"],
                "runtime_hours": a["runtime_hours"], "planned_bags": floor_units(a["planned_hours"] * rate),
                "capacity_bags": a["total"], "total_bags": a["total"], "good_bags": a["good"],
                "reject_bags": a["reject"], "scrap_kg": a["scrap_kg"],
                "lost_equipment_bags": floor_units(a["planned_hours"] * rate) - a["total"],
                "lost_material_bags": 0, "limiting_factor": "actual"})
    else:
        for r in sorted(runs, key=lambda r: (RUN_ORDER[r.run_type], r.line_id, r.seq, r.run_id)):
            pool = "ot" if r.run_type == "overtime" else "std"
            hours = max(0.0, min(r.hours, left[r.line_id][pool]))
            left[r.line_id][pool] -= hours
            sched[(r.line_id, pool)] += r.hours
            rate, yld = inputs.capability[(r.line_id, r.sku_id)]
            planned_qty = floor_units(r.hours * rate)
            cap_qty = floor_units(hours * rate)
            qty, limiting = cap_qty, None
            if enforce_materials:
                for m, per in sorted(inputs.recipes[r.sku_id].items()):
                    avail = state.raw.get((r.factory_id, m), 0.0)
                    if reserve is not None and r.run_type != "baseline":
                        avail -= reserve(r.factory_id, m, day)
                    avail = max(0.0, avail)
                    if cap_qty * per > avail + 1e-6:
                        shortfall[(r.factory_id, m)] += round(cap_qty * per - avail, 6)
                    max_q = floor_units(avail / per)
                    if max_q < qty:
                        qty, limiting = max_q, m
            good = floor_units(qty * yld)
            reject = qty - good
            consume(r.factory_id, r.sku_id, qty)
            runtime[(r.line_id, pool)] += qty / rate
            if r.ship_to:
                arrival = day + timedelta(days=int(round(inputs.params.get("transfer_lead_time_days", 1))))
                if good > 0:
                    state.in_transit.append({"sku_id": r.sku_id, "qty": good, "from": r.factory_id, "to": r.ship_to,
                                             "ship_date": day, "arrival_date": arrival, "run_id": r.run_id})
                    logs.transfers.append({"scenario_id": scenario_id, "run_id": r.run_id, "sku_id": r.sku_id,
                                           "from_factory_id": r.factory_id, "to_factory_id": r.ship_to,
                                           "ship_date": day, "arrival_date": arrival, "bags": good})
                shipped[(r.factory_id, r.sku_id)] += good
            else:
                state.fg[(r.factory_id, r.sku_id)] = state.fg.get((r.factory_id, r.sku_id), 0) + good
                to_stock[(r.factory_id, r.sku_id)] += good
            lost_material = cap_qty - qty
            lost_equipment = planned_qty - cap_qty
            logs.production.append({
                "scenario_id": scenario_id, "date": day, "phase": phase, "factory_id": r.factory_id,
                "line_id": r.line_id, "sku_id": r.sku_id, "run_id": r.run_id, "run_type": r.run_type,
                "ship_to": r.ship_to, "planned_hours": r.hours, "available_hours": hours,
                "runtime_hours": round(qty / rate, 6), "planned_bags": planned_qty, "capacity_bags": cap_qty,
                "total_bags": qty, "good_bags": good, "reject_bags": reject, "scrap_kg": scrap_kg(r.sku_id, reject),
                "lost_equipment_bags": lost_equipment, "lost_material_bags": lost_material,
                "limiting_factor": (f"material:{limiting}" if lost_material > 0
                                    else "equipment" if lost_equipment > 0 else "none")})

    for line, w in windows.items():
        rs, ro = runtime[(line, "std")], runtime[(line, "ot")]
        logs.line_days.append({
            "scenario_id": scenario_id, "date": day, "phase": phase, "factory_id": inputs.lines[line],
            "line_id": line, "planned_operating_hours": w["planned"], "downtime_hours": round(w["downtime"], 6),
            "standard_hours_available": round(w["std"], 6), "overtime_hours_available": w["ot"],
            "scheduled_standard_hours": round(sched[(line, "std")], 6),
            "scheduled_overtime_hours": round(sched[(line, "ot")], 6),
            "runtime_standard_hours": round(rs, 6), "runtime_overtime_hours": round(ro, 6),
            "runtime_hours": round(rs + ro, 6), "idle_standard_hours": round(max(0.0, w["std"] - rs), 6)})

    # 5. end-of-day allocation
    allocated = _allocate(state, inputs, day, scenario_id, logs)

    for k in _material_keys(inputs, state):
        logs.materials.append({
            "scenario_id": scenario_id, "date": day, "phase": phase, "factory_id": k[0], "material_id": k[1],
            "uom": inputs.materials[k[1]]["uom"], "category": inputs.materials[k[1]]["category"],
            "opening_qty": round(open_raw.get(k, 0.0), 6), "receipts_qty": round(receipts[k], 6),
            "consumed_qty": round(consumed[k], 6), "closing_qty": round(state.raw.get(k, 0.0), 6),
            "requested_shortfall_qty": round(shortfall[k], 6)})
    for k in _fg_keys(inputs, state):
        logs.finished_goods.append({
            "scenario_id": scenario_id, "date": day, "phase": phase, "factory_id": k[0], "sku_id": k[1],
            "opening_bags": open_fg.get(k, 0), "transfer_in_bags": transfer_in[k], "produced_to_stock_bags": to_stock[k],
            "produced_shipped_bags": shipped[k], "allocated_bags": allocated[k], "closing_bags": state.fg.get(k, 0)})



def replay_history(inputs: Inputs) -> tuple[State, Logs]:
    """Apply recorded actuals (Oct 25-26). Produces the shared decision-point state."""
    state, logs = new_state(inputs), Logs()
    for day in inputs.history_days:
        step_day(state, inputs, day, [], inputs.downtime_minor, "HISTORY", logs,
                 actuals=[a for a in inputs.actuals if a["date"] == day])
    return state, logs


def expected_run_qty(inputs: Inputs, runs: list, downtime: dict) -> dict:
    """Capacity-only expectation of each baseline run's total output given the known downtime estimate."""
    out = {}
    by_line_day = defaultdict(list)
    for r in runs:
        by_line_day[(r.line_id, r.date)].append(r)
    for (line, day), rs in by_line_day.items():
        left = line_windows(inputs, day, downtime)[line]["std"]
        for r in sorted(rs, key=lambda r: (r.seq, r.run_id)):
            h = max(0.0, min(r.hours, left))
            left -= h
            out[r.run_id] = floor_units(h * inputs.capability[(line, r.sku_id)][0])
    return out


def make_reserve(inputs: Inputs, baseline_runs: list, downtime: dict):
    """Time-phased reservation: the stock a recovery run must leave behind today so that every later
    baseline run stays feasible, netting scheduled PO receipts (max cumulative net requirement)."""
    expected = expected_run_qty(inputs, baseline_runs, downtime)
    need, receipts = defaultdict(float), defaultdict(float)
    for r in baseline_runs:
        for m, per in inputs.recipes[r.sku_id].items():
            need[(r.factory_id, m, r.date)] += expected[r.run_id] * per
    for p in inputs.purchase_orders:
        receipts[(p["factory_id"], p["material_id"], p["arrival_date"])] += p["qty"]

    def reserve(factory: str, material: str, day: date) -> float:
        cum, worst = 0.0, 0.0
        for d in inputs.days:
            if d > day:
                cum += need[(factory, material, d)] - receipts[(factory, material, d)]
                worst = max(worst, cum)
        return worst
    return reserve


def project_remaining(snapshot: State, inputs: Inputs, runs: list, downtime: dict) -> dict:
    """Planner's capacity-only projection from the decision-point state (no materials, standard yields)."""
    state, logs = copy.deepcopy(snapshot), Logs()
    for day in inputs.forward_days:
        step_day(state, inputs, day, [r for r in runs if r.date == day], downtime, "PLAN", logs,
                 enforce_materials=False)
    return state.remaining


def recovery_slots(inputs: Inputs, mode: str, baseline_runs: list, downtime: dict) -> list[dict]:
    affected = inputs.affected_factory
    slots = []
    for day in inputs.forward_days:
        windows = line_windows(inputs, day, downtime)
        for line in sorted(inputs.lines):
            f, w = inputs.lines[line], windows[line]
            if mode == "overtime" and f == affected:
                cap = w["ot"]
            elif mode == "transfer" and f != affected:
                cap = max(0.0, w["std"] - sum(r.hours for r in baseline_runs if r.line_id == line and r.date == day))
            else:
                continue
            slots.append({"line_id": line, "factory_id": f, "date": day, "mode": mode, "capacity_hours": cap,
                          "planned_hours": 0.0, "downtime_hours": w["downtime"],
                          "line_down_full_day": w["planned"] > 0 and w["downtime"] >= w["planned"] - EPS})
    return slots


def plan_recovery(snapshot: State, inputs: Inputs, mode: str, baseline_runs: list, downtime: dict,
                  scenario_id: str) -> tuple[list, list]:
    """Greedy, earliest-deadline-first recovery planner. Uses only decision-point information:
    the snapshot, the original plan, the breakdown estimate, standard rates/yields. Materials are NOT
    checked here; execution enforces them, which is how material constraints become visible."""
    affected = inputs.affected_factory
    lead = int(round(inputs.params.get("transfer_lead_time_days", 1))) if mode == "transfer" else 0
    slots = recovery_slots(inputs, mode, baseline_runs, downtime)
    runs, recovery = list(baseline_runs), []
    remaining = project_remaining(snapshot, inputs, runs, downtime)
    at_risk = sorted((o for o in inputs.orders if o.factory_id == affected and remaining[o.order_id] > 0),
                     key=lambda o: (o.deadline, o.created, o.order_id))
    for o in at_risk:
        while True:
            short = project_remaining(snapshot, inputs, runs, downtime)[o.order_id]
            if short <= 0:
                break
            slot = next((s for s in slots
                         if s["capacity_hours"] - s["planned_hours"] >= HOUR_STEP - EPS
                         and (s["line_id"], o.sku_id) in inputs.capability
                         and s["date"] + timedelta(days=lead) <= o.deadline), None)
            if slot is None:
                break
            rate, yld = inputs.capability[(slot["line_id"], o.sku_id)]
            need = math.ceil(short / (rate * yld) / HOUR_STEP - EPS) * HOUR_STEP
            hours = min(slot["capacity_hours"] - slot["planned_hours"], need)
            slot["planned_hours"] += hours
            run = Run(f"{scenario_id}-{mode.upper()}-{len(recovery) + 1:02d}", slot["date"], slot["factory_id"],
                      slot["line_id"], o.sku_id, hours, mode, 100 + len(recovery),
                      affected if mode == "transfer" else None)
            runs.append(run)
            recovery.append(run)
    for s in slots:
        latest_deadline = max((o.deadline for o in inputs.orders if o.factory_id == affected
                               and (s["line_id"], o.sku_id) in inputs.capability), default=None)
        s["timing_eligible"] = latest_deadline is not None and s["date"] + timedelta(days=lead) <= latest_deadline
    return recovery, slots


def apply_po_override(inputs: Inputs, override: tuple) -> Inputs:
    if not override:
        return inputs
    new_dates = dict(override)
    pos = [dict(p, arrival_date=new_dates.get(p["po_id"], p["arrival_date"])) for p in inputs.purchase_orders]
    return replace(inputs, purchase_orders=pos)


def run_scenario(inputs: Inputs, snapshot: State, history: Logs, sc: Scenario) -> ScenarioResult:
    inp = apply_po_override(inputs, sc.po_arrival_override)
    downtime = dict(inputs.downtime_minor)
    if sc.include_breakdown:
        for k, v in inputs.downtime_breakdown.items():
            downtime[k] = downtime.get(k, 0.0) + v
    baseline = [r for r in inp.plan_runs if r.date >= inp.decision_date]
    recovery, slots = (plan_recovery(snapshot, inp, sc.recovery, baseline, downtime, sc.scenario_id)
                       if sc.recovery else ([], []))
    reserve = make_reserve(inp, baseline, downtime)
    state = copy.deepcopy(snapshot)
    start_fp = state.fingerprint()
    logs = Logs()
    for name, rows in history.tables().items():
        getattr(logs, name).extend(dict(r, scenario_id=sc.scenario_id) for r in rows)
    runs = baseline + recovery
    plan_remaining = project_remaining(snapshot, inp, runs, downtime)
    for day in inp.forward_days:
        step_day(state, inp, day, [r for r in runs if r.date == day], downtime, sc.scenario_id, logs,
                 reserve=reserve)
    return ScenarioResult(sc, logs, state, start_fp, recovery, slots, downtime, plan_remaining)


def run_all_scenarios(inputs: Inputs, scenarios: list[Scenario] | None = None) -> dict[str, ScenarioResult]:
    snapshot, history = replay_history(inputs)
    scenarios = scenarios or default_scenarios(inputs.decision_date)
    return {sc.scenario_id: run_scenario(inputs, snapshot, history, sc) for sc in scenarios}
