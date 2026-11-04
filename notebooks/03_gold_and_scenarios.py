# Databricks notebook source
# MAGIC %md
# MAGIC # CandyOps 03 — Scenarios, sensitivity check → Gold
# MAGIC
# MAGIC **Decision (start of Oct 27, 2026):** packaging line NFD-A1 at Northfield is down until Oct 29 14:00.
# MAGIC Use overtime, move production to Southgate, or accept the shortfall?
# MAGIC
# MAGIC | Scenario | Meaning |
# MAGIC |---|---|
# MAGIC | S0_REFERENCE_NO_BREAKDOWN | Counterfactual only — shows which orders the breakdown puts at risk |
# MAGIC | S1_NO_RECOVERY | Disrupted original schedule, accept the shortfall |
# MAGIC | S2_OVERTIME | Up to 4 h overtime per line-day at Northfield where the line is running |
# MAGIC | S3_TRANSFER | Southgate's idle standard hours make compatible SKUs, trucked to Northfield (1-day lead time) |
# MAGIC | S3B_TRANSFER_EARLY_WRAPPERS | Sensitivity: S3 with Southgate's Halloween film delivered Oct 27 instead of Oct 30 |
# MAGIC | S4_OVERTIME_AND_TRANSFER | Overtime first, then Southgate's idle hours for what is still short |
# MAGIC
# MAGIC Sweeps (`gold_sweep`) rerun the options with one input changed: the film delivery date (Oct 27–30) and
# MAGIC the overtime cap (0–8 h per line-day). Every run is logged to MLflow.
# MAGIC
# MAGIC Every scenario restarts from the **same** state at the decision point (Oct 25–26 actuals replayed once).
# MAGIC The simulation is plain Python (`src/candyops/simulation.py`), deterministic and rule-based: no ML, no solver.
# MAGIC Results are **modeled outcomes on synthetic data**, not real savings and not customer delivery performance.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Catalog")
dbutils.widgets.text("schema", "candyops", "Project schema")
dbutils.widgets.text("repo_root", "", "Repo root (blank = parent of this notebook folder)")

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()

# COMMAND ----------

import os
import sys

REPO_ROOT = dbutils.widgets.get("repo_root").strip() or os.path.abspath(os.path.join(os.getcwd(), ".."))
SRC = os.path.join(REPO_ROOT, "src")
assert os.path.isdir(os.path.join(SRC, "candyops")), f"candyops package not found under {SRC}; set the repo_root widget"
if SRC not in sys.path:
    sys.path.insert(0, SRC)
for mod in [m for m in sys.modules if m == "candyops" or m.startswith("candyops.")]:
    del sys.modules[mod]

from candyops.pipeline import build_gold
from candyops.silver import SPEC
from candyops.spark_io import fqn, read_table, write_table

# COMMAND ----------

silver_tables = [stable for stable, _ in SPEC.values()] + ["silver_line_daily_downtime"]
silver = {t: read_table(spark, CATALOG, SCHEMA, t) for t in silver_tables}

gold = build_gold(silver)
written = [(name, write_table(spark, rows, CATALOG, SCHEMA, name)) for name, rows in gold.items()]
display(spark.createDataFrame(written, "table_name string, rows long"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Model-integrity checks (conservation, capacity, allocation, lead time, identical start state)

# COMMAND ----------

display(spark.sql(f"""
  SELECT status, COUNT(*) AS checks FROM {fqn(CATALOG, SCHEMA, 'gold_validation_results')} GROUP BY status"""))
display(spark.sql(f"""
  SELECT check_name, table_name, failed_rows, detail FROM {fqn(CATALOG, SCHEMA, 'gold_validation_results')}
  WHERE status <> 'PASS'"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Scenario comparison

# COMMAND ----------

display(spark.sql(f"""
  SELECT scenario_id, orders_fully_ready, bags_ordered, bags_ready_on_time, bags_short,
         ROUND(on_time_ready_rate_bags * 100, 1) AS on_time_ready_pct,
         incremental_cost_usd, incremental_ready_bags_vs_s1, cost_per_incremental_ready_bag_usd,
         seasonal_fg_remaining_bags, primary_constraint, constraint_detail
  FROM {fqn(CATALOG, SCHEMA, 'gold_scenario_summary')}
  ORDER BY scenario_id"""))

# COMMAND ----------

display(spark.table(fqn(CATALOG, SCHEMA, "gold_sensitivity")))
display(spark.sql(f"""
  SELECT scenario_id, `date`, line_id, spare_hours, recovery_hours_planned, recovery_runtime_hours,
         material_blocked_hours, unused_hours, status
  FROM {fqn(CATALOG, SCHEMA, 'gold_recovery_capacity')}
  WHERE spare_hours > 0 OR status LIKE 'unavailable%'
  ORDER BY scenario_id, `date`, line_id"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Sweeps: how late can the film arrive, and how much overtime is worth it?

# COMMAND ----------

display(spark.sql(f"""
  SELECT sweep_name, option, param_value, bags_ready_on_time,
         ROUND(on_time_ready_rate_bags * 100, 1) AS on_time_ready_pct,
         incremental_cost_usd, cost_per_incremental_ready_bag_usd, primary_constraint
  FROM {fqn(CATALOG, SCHEMA, 'gold_sweep')}
  ORDER BY sweep_name, option, days_or_hours"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Track every scenario and sweep point in MLflow
# MAGIC One parent run per pipeline run, one nested run per scenario, under `/Users/<you>/candyops-scenarios`.

# COMMAND ----------

from datetime import datetime, timezone

import mlflow

from candyops.tracking import log_runs, run_records

user = spark.sql("SELECT current_user()").first()[0]
experiment = f"/Users/{user}/candyops-scenarios"
records = run_records(gold)
parent_id = log_runs(mlflow, records, experiment, f"candyops-pipeline {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
print(f"Logged {len(records)} runs to MLflow experiment {experiment} (parent run {parent_id})")

# COMMAND ----------

failed = [r for r in gold["gold_validation_results"] if r["status"] != "PASS"]
if failed:
    raise RuntimeError(f"Gold integrity checks failed: {[r['check_name'] for r in failed]}")
print("Gold layer ready. Compare gold_scenario_summary with docs/results.md (local run) to verify Databricks parity.")
