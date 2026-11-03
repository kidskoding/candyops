"""End-to-end orchestration shared by the local runner and the Databricks notebooks."""

from __future__ import annotations

from .config import SEED
from .metrics import gold_tables
from .model import build_inputs
from .silver import normalize
from .simulation import run_all_scenarios
from .sources import generate_sources
from .validation import check_results, check_sources


def build_gold(silver: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """silver rows -> gold rows (scenarios, sensitivity, validation). Deterministic."""
    inputs = build_inputs(silver)
    results = run_all_scenarios(inputs)
    gold = gold_tables(inputs, results)
    gold["gold_validation_results"] = check_results(inputs, results)
    return gold


def run_local(seed: int = SEED) -> dict[str, dict[str, list[dict]]]:
    bronze = generate_sources(seed)
    silver = normalize(bronze)
    checks = check_sources(silver)
    return {"bronze": bronze, "silver": silver, "silver_checks": checks, "gold": build_gold(silver)}
