# Databricks notebook source
# MAGIC %md
# MAGIC # CandyOps 02 — Bronze → Silver + data-quality checks
# MAGIC
# MAGIC Casts the string exports to typed columns, splits downtime events into hours per line per day (clipped to the
# MAGIC 06:00–22:00 shift window), and runs key, reference, unit-of-measure, value-range and timestamp checks.
# MAGIC Failed checks are written to `silver_quality_checks`, displayed, and (by default) stop the pipeline.
# MAGIC **All data is synthetic.**

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Catalog")
dbutils.widgets.text("schema", "candyops", "Project schema")
dbutils.widgets.dropdown("fail_on_error", "true", ["true", "false"], "Stop if any check fails")
dbutils.widgets.text("repo_root", "", "Repo root (blank = parent of this notebook folder)")

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
FAIL_ON_ERROR = dbutils.widgets.get("fail_on_error") == "true"

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

from candyops.silver import SPEC, normalize
from candyops.spark_io import fqn, read_table, write_table
from candyops.validation import check_sources

# COMMAND ----------

bronze = {name: read_table(spark, CATALOG, SCHEMA, f"bronze_{name}") for name in SPEC}
silver = normalize(bronze)
for name, rows in silver.items():
    write_table(spark, rows, CATALOG, SCHEMA, name)

checks = check_sources(silver)
write_table(spark, checks, CATALOG, SCHEMA, "silver_quality_checks")
print(f"{len(silver)} silver tables written; {len(checks)} checks, "
      f"{sum(c['status'] != 'PASS' for c in checks)} failed")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Failed checks (empty = all passed)

# COMMAND ----------

display(spark.sql(f"""
  SELECT layer, check_name, table_name, failed_rows, detail
  FROM {fqn(CATALOG, SCHEMA, 'silver_quality_checks')}
  WHERE status <> 'PASS'
  ORDER BY table_name, check_name"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Independent SQL cross-checks (Spark, not Python)

# COMMAND ----------

sql_checks = spark.sql(f"""
  SELECT 'orders_with_unknown_sku' AS check_name, COUNT(*) AS failed_rows
  FROM {fqn(CATALOG, SCHEMA, 'silver_customer_orders')} o
  LEFT ANTI JOIN {fqn(CATALOG, SCHEMA, 'silver_products')} p ON o.sku_id = p.sku_id
  UNION ALL
  SELECT 'batches_where_good_plus_reject_ne_total', COUNT(*)
  FROM {fqn(CATALOG, SCHEMA, 'silver_production_actuals')} a
  JOIN {fqn(CATALOG, SCHEMA, 'silver_quality_inspections')} q ON a.batch_id = q.batch_id
  WHERE q.good_bags + q.rejected_bags <> a.total_bags
  UNION ALL
  SELECT 'po_uom_mismatch', COUNT(*)
  FROM {fqn(CATALOG, SCHEMA, 'silver_purchase_orders')} po
  JOIN {fqn(CATALOG, SCHEMA, 'silver_materials')} m ON po.material_id = m.material_id
  WHERE po.uom <> m.uom
  UNION ALL
  SELECT 'downtime_end_not_after_start', COUNT(*)
  FROM {fqn(CATALOG, SCHEMA, 'silver_downtime_events')} WHERE end_ts <= start_ts
""")
display(sql_checks)
sql_failures = [r.check_name for r in sql_checks.collect() if r.failed_rows > 0]

# COMMAND ----------

display(spark.table(fqn(CATALOG, SCHEMA, "silver_line_daily_downtime")).orderBy("line_id", "downtime_date"))

# COMMAND ----------

failed = [c["check_name"] for c in checks if c["status"] != "PASS"] + sql_failures
if failed and FAIL_ON_ERROR:
    raise RuntimeError(f"Silver data-quality checks failed: {sorted(set(failed))}")
print("Silver layer ready." if not failed else f"Continuing despite failed checks: {failed}")
