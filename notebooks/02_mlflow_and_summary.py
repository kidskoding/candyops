# Databricks notebook source
# MAGIC %md
# MAGIC # candyops 02: Results to MLflow
# MAGIC
# MAGIC Runs after `dbt build`. Logs one MLflow run per candy-bowl restriction and per matching method, with the
# MAGIC dataset versions as parameters, so runs can be compared over time in the experiment UI.

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

import mlflow

from candyops.config import DATA_NOTICE, OFF_DATASET, RANKING_DATASET
from candyops.spark_io import fqn
from candyops.tracking import log_runs, run_records

print(DATA_NOTICE)

# COMMAND ----------


def rows(table):
    return [r.asDict() for r in spark.table(fqn(CATALOG, SCHEMA, table)).collect()]


bowls = rows("gold_bowl_summary")
match_methods = rows("gold_match_methods")
display(spark.table(fqn(CATALOG, SCHEMA, "gold_bowl_summary")).orderBy("popularity_kept_pct", ascending=False))
display(spark.table(fqn(CATALOG, SCHEMA, "gold_match_methods")))

# COMMAND ----------

user = spark.sql("SELECT current_user()").first()[0]
run_id = log_runs(mlflow, run_records(bowls, match_methods), f"/Users/{user}/candyops-candy-bowls",
                  f"pipeline-{SCHEMA}",
                  {"off_dataset": OFF_DATASET, "ranking_dataset": RANKING_DATASET, "schema": SCHEMA})
print(f"MLflow parent run {run_id}: {len(bowls)} bowls, {len(match_methods)} matching methods")

# COMMAND ----------

# MAGIC %md
# MAGIC ## One bowl for the whole street
# MAGIC
# MAGIC Picks the 10 candies that give the most kids a favorite they can eat, weighting peanut, milk and tree-nut
# MAGIC allergies by how common they are in US children, and compares that bowl with the regular top 10.

# COMMAND ----------

from candyops.street_bowl import PREVALENCE, coverage, expected_win, kid_groups, street_bowl

win = {r["candy"]: r["win_percent"] for r in rows("gold_candy_profile")}
safe = {a: set() for a in PREVALENCE}
for r in rows("gold_allergy_safe_candies"):
    if r["allergen"] in safe:
        safe[r["allergen"]].add(r["candy"])

groups = kid_groups()
bowl = street_bowl(win, safe)
regular = sorted(win, key=lambda c: (-win[c], c))[:10]
metrics = {
    "street_expected_win": expected_win(bowl, win, safe, groups),
    "regular_expected_win": expected_win(regular, win, safe, groups),
    "street_avg_win": sum(win[c] for c in bowl) / len(bowl),
    "regular_avg_win": sum(win[c] for c in regular) / len(regular),
    **{f"street_options_{a}": n for a, n in coverage(bowl, safe).items()},
    **{f"regular_options_{a}": n for a, n in coverage(regular, safe).items()},
}

spark.createDataFrame(
    [(i + 1, c, float(win[c]), [a for a in PREVALENCE if c in safe[a]], c in regular) for i, c in enumerate(bowl)],
    "bowl_rank INT, candy STRING, win_percent DOUBLE, safe_for ARRAY<STRING>, in_regular_bowl BOOLEAN",
).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(fqn(CATALOG, SCHEMA, "gold_street_bowl"))

with mlflow.start_run(run_name=f"street-bowl-{SCHEMA}"):
    mlflow.set_tags({"project": "candyops", "run_type": "street_bowl"})
    mlflow.log_params({**{f"prevalence_{a}": p for a, p in PREVALENCE.items()}, "bowl_size": len(bowl)})
    mlflow.log_metrics(metrics)
display(spark.table(fqn(CATALOG, SCHEMA, "gold_street_bowl")))
print(metrics)
