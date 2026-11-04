# Databricks notebook source
# MAGIC %md
# MAGIC # candyops 01b: Open Food Facts change feed to Bronze (incremental)
# MAGIC
# MAGIC Open Food Facts publishes one file per day with every product edited that day and keeps only about two
# MAGIC weeks of files. This notebook:
# MAGIC
# MAGIC 1. **Archives** each new daily file into the Unity Catalog volume, so the project keeps files after they
# MAGIC    expire upstream. Files already archived are skipped; downloads land as `.part` and are renamed when complete.
# MAGIC 2. **Loads incrementally** with Auto Loader (`availableNow`): the checkpoint remembers which files are in
# MAGIC    `bronze_off_changes`, so each file is appended exactly once, however often the job runs.
# MAGIC 3. **Records the archive** in `bronze_off_change_files`; dbt warns when consecutive files leave a gap.

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
    del sys.modules[mod]

import shutil
import urllib.request

from pyspark.sql import functions as F

from candyops.config import FEED_BASE_URL, FEED_SCHEMA
from candyops.sources import feed_files, feed_gaps
from candyops.spark_io import fqn

# COMMAND ----------

fqn(CATALOG, SCHEMA, VOLUME)
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`.`{VOLUME}`")
ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"
ARCHIVE = f"{ROOT}/off_change_feed"
CHECKPOINT = f"{ROOT}/_checkpoints/bronze_off_changes"
os.makedirs(ARCHIVE, exist_ok=True)

index = urllib.request.urlopen(FEED_BASE_URL + "index.txt", timeout=60).read().decode().split()
new = [f for f in feed_files(index) if not os.path.exists(f"{ARCHIVE}/{f['file_name']}")]
for f in new:
    part = f"/tmp/{f['file_name']}.part"
    with urllib.request.urlopen(FEED_BASE_URL + f["file_name"], timeout=300) as r, open(part, "wb") as out:
        shutil.copyfileobj(r, out)
    shutil.move(part, f"{ARCHIVE}/{f['file_name']}")
print(f"upstream lists {len(index)} files; archived {len(new)} new")

# COMMAND ----------

query = (spark.readStream.format("cloudFiles")
         .option("cloudFiles.format", "json")
         .option("pathGlobFilter", "*.json.gz")
         .schema(FEED_SCHEMA)
         .load(ARCHIVE)
         .withColumn("_source_file", F.col("_metadata.file_name"))
         .withColumn("_ingested_at", F.current_timestamp())
         .writeStream
         .option("checkpointLocation", CHECKPOINT)
         .trigger(availableNow=True)
         .toTable(fqn(CATALOG, SCHEMA, "bronze_off_changes")))
query.awaitTermination()
print(f"bronze_off_changes: {spark.table(fqn(CATALOG, SCHEMA, 'bronze_off_changes')).count():,} rows")

# COMMAND ----------

archived = feed_files(os.listdir(ARCHIVE))
spark.createDataFrame(archived, "file_name STRING, from_ts LONG, to_ts LONG") \
    .write.mode("overwrite").saveAsTable(fqn(CATALOG, SCHEMA, "bronze_off_change_files"))
gaps = feed_gaps(archived)
print(f"archive holds {len(archived)} files; gaps: {gaps or 'none'}")
