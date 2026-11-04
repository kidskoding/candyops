"""End-to-end orchestration shared by the local runner and the Databricks notebooks."""

from __future__ import annotations

from .config import SEED
from .metrics import BASE_OPTION, gold_tables, sweep_table
from .model import build_inputs
from .silver import normalize
from .simulation import default_scenarios, run_all_scenarios, sweep_scenarios
from .sources import generate_sources
from .validation import check_results, check_sources


def build_gold(silver: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """silver rows -> gold rows (scenarios, sensitivity, validation). Deterministic."""
    inputs = build_inputs(silver)
    scenarios = default_scenarios(inputs.decision_date) + sweep_scenarios(inputs.decision_date)
    results = run_all_scenarios(inputs, scenarios)
    main = {k: r for k, r in results.items() if r.scenario.kind != "sweep"}
    sweeps = {k: r for k, r in results.items() if r.scenario.kind == "sweep" or k == BASE_OPTION}
    gold = gold_tables(inputs, main)
    gold["gold_sweep"] = sweep_table(inputs, sweeps)
    gold["gold_validation_results"] = check_results(inputs, results)
    return gold


def run_local(seed: int = SEED) -> dict[str, dict[str, list[dict]]]:
    bronze = generate_sources(seed)
    silver = normalize(bronze)
    checks = check_sources(silver)
    return {"bronze": bronze, "silver": silver, "silver_checks": checks, "gold": build_gold(silver)}
