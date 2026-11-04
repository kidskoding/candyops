"""MLflow tracking for the dbt gold tables. mlflow is passed in, so this module imports without it."""

from __future__ import annotations

BOWL_METRICS = ("candies_allowed", "avg_win_percent", "popularity_kept_pct", "median_sugars_100g")
MATCH_METRICS = ("candies_matched", "products_matched", "us_products_matched", "non_candy_products")


def _metrics(row: dict, keys: tuple[str, ...]) -> dict:
    return {k: float(row[k]) for k in keys if row.get(k) is not None}


def run_records(bowls: list[dict], match_methods: list[dict]) -> list[dict]:
    """One record per bowl restriction and per matching method."""
    records = [{"run_name": f"bowl:{b['restriction']}",
                "params": {"run_type": "bowl", "restriction": b["restriction"], "bowl": b["bowl"]},
                "metrics": _metrics(b, BOWL_METRICS)}
               for b in bowls]
    records += [{"run_name": f"match:{m['method']}",
                 "params": {"run_type": "matching", "method": m["method"]},
                 "metrics": _metrics(m, MATCH_METRICS)}
                for m in match_methods]
    return records


def log_runs(mlflow, records: list[dict], experiment_path: str, parent_run_name: str, params: dict) -> str:
    """One parent run per pipeline run, one nested run per record."""
    mlflow.set_experiment(experiment_path)
    with mlflow.start_run(run_name=parent_run_name) as parent:
        mlflow.set_tags({"project": "candyops", "data_source": "kaggle"})
        mlflow.log_params(params)
        for rec in records:
            with mlflow.start_run(run_name=rec["run_name"], nested=True):
                mlflow.log_params(rec["params"])
                mlflow.log_metrics(rec["metrics"])
        return parent.info.run_id
