"""Regenerate docs/results.md from the gold tables on Databricks (uses the databricks CLI's auth).

    uv run python scripts/write_results.py [--profile NAME] [--schema candyops]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = "Serverless Starter Warehouse"


def cli(args: list[str], profile: str | None) -> dict | list:
    cmd = ["databricks", *args, "-o", "json"] + (["--profile", profile] if profile else [])
    return json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)


def query(sql: str, warehouse: str, profile: str | None) -> list[dict]:
    body = {"warehouse_id": warehouse, "statement": sql, "wait_timeout": "50s", "format": "JSON_ARRAY"}
    res = cli(["api", "post", "/api/2.0/sql/statements", "--json", json.dumps(body)], profile)
    if res["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(f"{sql[:60]}...: {res['status']}")
    cols = [c["name"] for c in res["manifest"]["schema"]["columns"]]
    return [dict(zip(cols, row, strict=True)) for row in res.get("result", {}).get("data_array", [])]


def table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    out = "| " + " | ".join(h for _, h in cols) + " |\n|" + "---|" * len(cols) + "\n"
    for r in rows:
        out += "| " + " | ".join("" if r[k] is None else str(r[k]) for k, _ in cols) + " |\n"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile")
    ap.add_argument("--catalog", default="workspace")
    ap.add_argument("--schema", default="candyops")
    a = ap.parse_args()
    wh = next(w["id"] for w in cli(["warehouses", "list"], a.profile) if w["name"] == WAREHOUSE)
    s = f"`{a.catalog}`.`{a.schema}`"

    def q(sql):
        return query(sql.format(s=s), wh, a.profile)

    quality = q("SELECT metric, value FROM {s}.gold_data_quality ORDER BY sort_order")
    bowls = q("SELECT restriction, candies_allowed, avg_win_percent, popularity_kept_pct, median_sugars_100g, bowl "
              "FROM {s}.gold_bowl_summary ORDER BY popularity_kept_pct DESC, restriction")
    methods = q("SELECT * FROM {s}.gold_match_methods ORDER BY method DESC")
    candies = q("SELECT popularity_rank, candy, win_percent, n_products, n_evidence, evidence_scope, peanut, tree_nut, "
                "milk, gluten, soy, egg, sugars_100g FROM {s}.gold_candy_profile ORDER BY popularity_rank, candy")
    changes = q("SELECT candy, allergen, status_2017, evidence_2017, status_now, evidence_now, comparison "
                "FROM {s}.gold_label_changes WHERE comparison IN ('changed', 'newly_covered') "
                "ORDER BY comparison, candy, allergen")
    coverage = q("SELECT outcome, count(*) AS candies FROM (SELECT candy, CASE "
                 "WHEN max(comparison = 'changed') THEN 'at least one allergen changed' "
                 "WHEN max(comparison = 'newly_covered') THEN 'newly covered' "
                 "WHEN max(comparison = 'unchanged') THEN 'all compared allergens unchanged' "
                 "ELSE 'not enough current data' END AS outcome "
                 "FROM {s}.gold_label_changes GROUP BY candy) GROUP BY outcome ORDER BY candies DESC")
    when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    md = f"""# CandyOps results

**Executed** {when} against `{a.catalog}.{a.schema}` on Databricks (regenerate: `scripts/write_results.py`).

Data: Open Food Facts (ODbL) and FiveThirtyEight's Candy Power Ranking (MIT), 2017 snapshots from Kaggle, plus the
Open Food Facts daily change feed (products edited since the feed archive started).
Allergen statuses are parsed from crowdsourced ingredient lists, are not medical advice, and can be out of date.

## 1. Cleaning

{table(quality, [("metric", "Metric"), ("value", "Value")])}
## 2. Bowls

Each bowl holds the 10 most popular candies whose matched labels list none of the
restricted allergens (on at least 2 products with an ingredient list). `popularity_kept_pct` compares the bowl's average
win rate with the unrestricted bowl's.

{table(bowls, [("restriction", "Restriction"), ("candies_allowed", "Candies allowed"),
               ("avg_win_percent", "Avg win %"), ("popularity_kept_pct", "Popularity kept %"),
               ("median_sugars_100g", "Median sugar g/100g"), ("bowl", "Bowl, most popular first")])}
## 3. Matching: name only vs curated rules

{table(methods, [("method", "Method"), ("candies_matched", "Candies matched"), ("candies_total", "Of"),
                 ("products_matched", "Products"), ("us_products_matched", "US products"),
                 ("non_candy_products", "Not candy")])}
## 4. Is the 2017 answer still true?

Allergen status per candy in the 2017 snapshot next to the products edited since the change feed started. A candy is
compared only when it has at least 2 current products with an ingredient list; the bowls above still use 2017.

{table(coverage, [("outcome", "Each candy, 2017 vs now"), ("candies", "Candies")])}
{table(changes, [("candy", "Candy"), ("allergen", "Allergen"), ("status_2017", "2017"),
                 ("evidence_2017", "2017 products"), ("status_now", "Now"),
                 ("evidence_now", "Current products"), ("comparison", "Comparison")])}
## 5. Every candy

Statuses: `contains` (most evidence lists it), `varies` (some products do), `may_contain` (warning only),
`not_listed`, `unknown` (no matched product with an ingredient list).

{table(candies, [("popularity_rank", "Rank"), ("candy", "Candy"), ("win_percent", "Win %"),
                 ("n_products", "Products"), ("n_evidence", "With ingredients"), ("evidence_scope", "Scope"),
                 ("peanut", "Peanut"), ("tree_nut", "Tree nut"), ("milk", "Milk"), ("gluten", "Gluten"),
                 ("soy", "Soy"), ("egg", "Egg"), ("sugars_100g", "Sugar g/100g")])}"""
    (ROOT / "docs" / "results.md").write_text(md)
    print(f"docs/results.md written from {a.catalog}.{a.schema}")


if __name__ == "__main__":
    main()
