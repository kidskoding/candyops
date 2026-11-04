# Databricks notebook source
# MAGIC %md
# MAGIC # candyops 01: Kaggle to Bronze
# MAGIC
# MAGIC Downloads two pinned public Kaggle datasets into a Unity Catalog volume and loads them, unchanged and as
# MAGIC strings, into bronze Delta tables:
# MAGIC
# MAGIC | Kaggle dataset | Bronze table | Shape |
# MAGIC |---|---|---|
# MAGIC | `openfoodfacts/world-food-facts` v5 (ODbL) | `bronze_off_products` | 356,001 products x 163 columns, ~1 GB TSV |
# MAGIC | `fivethirtyeight/the-ultimate-halloween-candy-power-ranking` v1 (MIT) | `bronze_candy_ranking` | 85 candies |
# MAGIC
# MAGIC dbt builds silver and gold from these tables. Re-running reuses the files cached in the volume and skips
# MAGIC installing kagglehub; it is installed only when a file is missing.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Catalog")
dbutils.widgets.text("schema", "candyops", "Project schema")
dbutils.widgets.text("volume", "raw", "Volume for raw downloads")
dbutils.widgets.text("repo_root", "", "Repo root (blank = parent of this notebook folder)")

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
VOLUME = dbutils.widgets.get("volume").strip()

# COMMAND ----------

import os
import sys

REPO_ROOT = dbutils.widgets.get("repo_root").strip() or os.path.abspath(os.path.join(os.getcwd(), ".."))
SRC = os.path.join(REPO_ROOT, "src")
assert os.path.isdir(os.path.join(SRC, "candyops")), f"candyops package not found under {SRC}; set the repo_root widget"
if SRC not in sys.path:
    sys.path.insert(0, SRC)
for mod in [m for m in sys.modules if m == "candyops" or m.startswith("candyops.")]:
    del sys.modules[mod]  # pick up edits on rerun

from pyspark.sql import functions as F

from candyops.config import DATA_NOTICE, OFF_DATASET, OFF_ROWS, RANKING_DATASET, RANKING_ROWS
from candyops.sources import OFF_READ_OPTIONS, RANKING_READ_OPTIONS, download
from candyops.spark_io import fqn

print(DATA_NOTICE)

# COMMAND ----------

fqn(CATALOG, SCHEMA, VOLUME)  # validates identifiers before they reach SQL
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}` "
          "COMMENT 'candyops: Halloween candy and food allergies, from public Kaggle data'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`.`{VOLUME}`")

off_path, ranking_path = download(f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/kagglehub")
print(off_path, ranking_path, sep="\n")

# COMMAND ----------


def load(path, options, dataset, table, expected_rows):
    name = fqn(CATALOG, SCHEMA, table)
    if spark.catalog.tableExists(name.replace("`", "")) and spark.table(name).count() == expected_rows:
        return expected_rows  # pinned snapshot already loaded; the daily job skips the 1 GB reload
    df = (spark.read.options(**options).csv(path)
          .withColumn("_source_dataset", F.lit(dataset))
          .withColumn("_ingested_at", F.current_timestamp()))
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(fqn(CATALOG, SCHEMA, table))
    return spark.table(fqn(CATALOG, SCHEMA, table)).count()


n_off = load(off_path, OFF_READ_OPTIONS, OFF_DATASET, "bronze_off_products", OFF_ROWS)
n_rank = load(ranking_path, RANKING_READ_OPTIONS, RANKING_DATASET, "bronze_candy_ranking", RANKING_ROWS)
print(f"bronze_off_products: {n_off:,} rows; bronze_candy_ranking: {n_rank} rows")
assert (n_off, n_rank) == (OFF_ROWS, RANKING_ROWS), "row counts differ from the pinned Kaggle files"
