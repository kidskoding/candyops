# Databricks notebook source
# MAGIC %md
# MAGIC # CandyOps 01 — Simulated source exports → Bronze
# MAGIC
# MAGIC **SYNTHETIC DATA.** Every factory, retailer, order, cost and quantity is fictional and produced by a seeded
# MAGIC generator. The feeds below *imitate* ERP / MES / WMS-procurement / QMS flat-file exports; there is no SAP,
# MAGIC Oracle or other real integration. No affiliation with any confectionery company is implied.
# MAGIC
# MAGIC | Source area | Bronze tables |
# MAGIC |---|---|
# MAGIC | ERP | factories, products, materials & costs, recipes (BOM), customer orders, production orders, cost parameters |
# MAGIC | MES | lines, line capability (rates/yields), line calendar, downtime events, production actuals |
# MAGIC | Inventory & procurement | opening raw materials, opening finished goods, supplier purchase orders |
# MAGIC | Quality | batch inspections (good, rejected, scrap) |
# MAGIC
# MAGIC Bronze keeps values as strings, exactly as exported. Re-running overwrites only `bronze_*` tables in the
# MAGIC project schema.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Catalog")
dbutils.widgets.text("schema", "candyops", "Project schema")
dbutils.widgets.text("seed", "20261027", "Random seed")
dbutils.widgets.text("repo_root", "", "Repo root (blank = parent of this notebook folder)")

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
SEED = int(dbutils.widgets.get("seed"))

# COMMAND ----------

# Make src/ importable. In a Databricks Git folder (or workspace folder) the notebook's working directory is
# the notebook's own folder, so the repo root is its parent.
import os
import sys

REPO_ROOT = dbutils.widgets.get("repo_root").strip() or os.path.abspath(os.path.join(os.getcwd(), ".."))
SRC = os.path.join(REPO_ROOT, "src")
assert os.path.isdir(os.path.join(SRC, "candyops")), f"candyops package not found under {SRC}; set the repo_root widget"
if SRC not in sys.path:
    sys.path.insert(0, SRC)
for mod in [m for m in sys.modules if m == "candyops" or m.startswith("candyops.")]:
    del sys.modules[mod]  # pick up edits on rerun

from candyops.config import SYNTHETIC_NOTICE
from candyops.sources import generate_sources
from candyops.spark_io import fqn, write_table

print(SYNTHETIC_NOTICE)

# COMMAND ----------

fqn(CATALOG, SCHEMA, "probe")  # validates identifiers before they reach SQL
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}` COMMENT 'CandyOps synthetic Halloween manufacturing demo'")

bronze = generate_sources(SEED)
counts = []
for name, rows in bronze.items():
    n = write_table(spark, rows, CATALOG, SCHEMA, f"bronze_{name}")
    counts.append((f"bronze_{name}", rows[0]["_source_system"], n))

display(spark.createDataFrame(counts, "table_name string, source_system string, rows long"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Quick look: the order book and the breakdown event

# COMMAND ----------

display(spark.table(fqn(CATALOG, SCHEMA, "bronze_erp_customer_orders"))
        .select("order_id", "customer_name", "dispatch_factory_id", "sku_id", "order_qty_bags", "ready_to_ship_deadline")
        .orderBy("ready_to_ship_deadline", "order_id"))
display(spark.table(fqn(CATALOG, SCHEMA, "bronze_mes_downtime_events")).where("event_type LIKE 'breakdown%'"))
