"""MLflow experiment tracking for scenario and sweep results. mlflow is passed in, so this runs without it."""

from __future__ import annotations

METRICS = ("bags_ready_on_time", "on_time_ready_rate_bags", "orders_fully_ready", "incremental_cost_usd",
           "incremental_ready_bags_vs_s1", "cost_per_incremental_ready_bag_usd", "seasonal_fg_remaining_bags",
           "overtime_runtime_hours", "alternate_runtime_hours")


def _metrics(row: dict) -> dict:
    return {k: float(row[k]) for k in METRICS if row.get(k) is not None}


def run_records(gold: dict[str, list[dict]]) -> list[dict]:
    records = [{"run_name": s["scenario_id"],
                "params": {"run_type": "scenario", "scenario_kind": s["scenario_kind"],
                           "scenario_name": s["scenario_name"]},
                "metrics": _metrics(s),
                "tags": {"primary_constraint": s["primary_constraint"]}}
               for s in gold["gold_scenario_summary"]]
    records += [{"run_name": r["scenario_id"],
                 "params": {"run_type": "sweep", "sweep_name": r["sweep_name"], "option": r["option"],
                            "param_value": r["param_value"]},
                 "metrics": _metrics(r),
                 "tags": {"primary_constraint": r["primary_constraint"]}}
                for r in gold["gold_sweep"]]
    return records


def log_runs(mlflow, records: list[dict], experiment_path: str, parent_run_name: str) -> str:
    """One parent run per pipeline run, one nested run per scenario or sweep point."""
    mlflow.set_experiment(experiment_path)
    with mlflow.start_run(run_name=parent_run_name) as parent:
        mlflow.set_tags({"project": "candyops", "synthetic_data": "true"})
        for rec in records:
            with mlflow.start_run(run_name=rec["run_name"], nested=True):
                mlflow.log_params(rec["params"])
                mlflow.log_metrics(rec["metrics"])
                mlflow.set_tags({**rec["tags"], "synthetic_data": "true"})
        return parent.info.run_id
