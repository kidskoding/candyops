"""Local Spark + Delta smoke test that mirrors notebooks 01 -> 02 -> 03 (NOT a Databricks verification).

    uv run --group spark python scripts/spark_smoke.py

Needs Java 17+. Writes Delta tables under out/spark-warehouse. Checks that the Delta round trip
(bronze strings -> silver typed -> gold) reproduces the pure-Python results exactly.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from delta import configure_spark_with_delta_pip  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402

from candyops.pipeline import build_gold, run_local  # noqa: E402
from candyops.silver import SPEC, normalize  # noqa: E402
from candyops.sources import generate_sources  # noqa: E402
from candyops.spark_io import fqn, read_table, write_table  # noqa: E402
from candyops.validation import check_sources  # noqa: E402

CATALOG, SCHEMA = "spark_catalog", "candyops"
WAREHOUSE = ROOT / "out" / "spark-warehouse"


def main() -> int:
    shutil.rmtree(WAREHOUSE, ignore_errors=True)
    builder = (SparkSession.builder.master("local[2]").appName("candyops-smoke")
               .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
               .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
               .config("spark.sql.warehouse.dir", str(WAREHOUSE))
               .config("spark.sql.session.timeZone", "UTC")
               .config("spark.ui.enabled", "false"))
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")

    for name, rows in generate_sources().items():
        write_table(spark, rows, CATALOG, SCHEMA, f"bronze_{name}")
    bronze = {name: read_table(spark, CATALOG, SCHEMA, f"bronze_{name}") for name in SPEC}
    silver = normalize(bronze)
    for name, rows in silver.items():
        write_table(spark, rows, CATALOG, SCHEMA, name)
    checks = check_sources(silver)
    write_table(spark, checks, CATALOG, SCHEMA, "silver_quality_checks")
    silver_back = {t: read_table(spark, CATALOG, SCHEMA, t)
                   for t in [s for s, _ in SPEC.values()] + ["silver_line_daily_downtime"]}
    gold = build_gold(silver_back)
    for name, rows in gold.items():
        write_table(spark, rows, CATALOG, SCHEMA, name)

    # rerun safety: second write overwrites, row counts unchanged
    write_table(spark, gold["gold_scenario_summary"], CATALOG, SCHEMA, "gold_scenario_summary")
    n = spark.table(fqn(CATALOG, SCHEMA, "gold_scenario_summary")).count()

    local = run_local()["gold"]
    same = gold["gold_scenario_summary"] == local["gold_scenario_summary"] and \
        gold["gold_sensitivity"] == local["gold_sensitivity"]
    fails = [c for c in checks + gold["gold_validation_results"] if c["status"] != "PASS"]
    spark.sql(f"SELECT scenario_id, bags_ready_on_time, incremental_cost_usd, primary_constraint "
              f"FROM {fqn(CATALOG, SCHEMA, 'gold_scenario_summary')} ORDER BY scenario_id").show(truncate=False)
    # every dashboard dataset must parse and return rows against the Delta tables
    sql_text = (ROOT / "sql" / "dashboard_queries.sql").read_text()
    body = "\n".join(l for l in sql_text.splitlines() if not l.strip().startswith("--"))
    queries = [q.strip() for q in body.split(";") if q.strip()]
    empty = []
    for q in queries:
        if spark.sql(q.replace("workspace.candyops.", f"{CATALOG}.{SCHEMA}.")).count() == 0:
            empty.append(q[:80])
    print(f"dashboard queries run: {len(queries)}; empty results: {empty}")
    tables = spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`").count()
    print(f"delta tables: {tables}; summary rows after rerun: {n}; failed checks: {len(fails)}; "
          f"matches pure-Python run: {same}")
    spark.stop()
    return 0 if same and not fails and n == 5 and not empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
