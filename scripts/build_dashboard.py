"""Write dashboards/candyops.lvdash.json (AI/BI dashboard over the dbt gold tables).

    uv run python scripts/build_dashboard.py
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "dashboards" / "candyops.lvdash.json"

LABEL = """CASE restriction
    WHEN 'no_restriction' THEN '1 No restriction'
    WHEN 'peanut_free' THEN '2 Peanut-free'
    WHEN 'nut_free' THEN '3 Nut-free'
    WHEN 'milk_free' THEN '4 Milk-free'
    WHEN 'gluten_free' THEN '5 Gluten-free'
    WHEN 'free_of_all_six' THEN '6 Free of all six'
  END"""


def ql(sql):
    lines = sql.strip("\n").split("\n")
    return [ln + "\n" for ln in lines[:-1]] + [lines[-1]]


DATASETS = [
    {"name": "ds_kpi", "displayName": "Headline numbers", "queryLines": ql("""
SELECT
  MAX(CASE WHEN metric = 'bronze_rows' THEN value END) AS products_scanned,
  MAX(CASE WHEN metric = 'duplicate_barcode_rows_dropped' THEN value END) AS duplicates_dropped,
  MAX(CASE WHEN metric = 'candies_with_enough_evidence' THEN value END) AS candies_with_evidence,
  MAX(CASE WHEN metric = 'ranked_candies' THEN value END) AS ranked_candies,
  (SELECT popularity_kept_pct / 100 FROM gold_bowl_summary WHERE restriction = 'peanut_free') AS peanut_free_kept,
  (SELECT popularity_kept_pct / 100 FROM gold_bowl_summary WHERE restriction = 'free_of_all_six') AS all_six_kept
FROM gold_data_quality""")},
    {"name": "ds_bowls", "displayName": "Bowls by restriction", "queryLines": ql(f"""
SELECT
  {LABEL} AS restriction_label,
  candies_allowed,
  avg_win_percent,
  popularity_kept_pct / 100 AS popularity_kept,
  median_sugars_100g,
  bowl
FROM gold_bowl_summary
ORDER BY restriction_label""")},
    {"name": "ds_candies", "displayName": "Candy profiles", "queryLines": ql("""
SELECT
  popularity_rank,
  candy,
  win_percent / 100 AS win_rate,
  n_products,
  n_evidence,
  evidence_scope,
  peanut,
  tree_nut,
  milk,
  gluten,
  soy,
  egg,
  sugars_100g
FROM gold_candy_profile
ORDER BY popularity_rank, candy""")},
    {"name": "ds_methods", "displayName": "Matching methods", "queryLines": ql("""
SELECT
  CASE method WHEN 'naive' THEN 'Name only' ELSE 'Curated rules' END AS method_label,
  candies_matched,
  candies_total,
  products_matched,
  us_products_matched,
  non_candy_products
FROM gold_match_methods
ORDER BY method_label DESC""")},
    {"name": "ds_quality", "displayName": "Data quality", "queryLines": ql("""
SELECT sort_order, replace(metric, '_', ' ') AS metric, value
FROM gold_data_quality
ORDER BY sort_order""")},
    {"name": "ds_changes", "displayName": "2017 versus now", "queryLines": ql("""
SELECT
  candy,
  replace(allergen, '_', ' ') AS allergen,
  status_2017,
  status_now,
  evidence_2017,
  evidence_now,
  CASE comparison WHEN 'changed' THEN 'Changed' ELSE 'Newly covered' END AS comparison_label
FROM gold_label_changes
WHERE comparison IN ('changed', 'newly_covered')
ORDER BY comparison, candy, allergen""")},
]

PCT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}
CNT = {"type": "number", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 1}}
ORANGE, PURPLE, GREY, AMBER, LAVENDER = "#F97316", "#7C3AED", "#8B8B99", "#FDBA74", "#C4B5FD"


def q(ds, cols):
    return [{"name": "main_query", "query": {"datasetName": ds,
             "fields": [{"name": c, "expression": f"`{c}`"} for c in cols], "disaggregated": True}}]


def pos(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def text(name, lines, x, y, w, h):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": lines}}, "position": pos(x, y, w, h)}


def counter(name, title, col, fmt, x, description, template=None):
    enc = {"fieldName": col, "displayName": title, "format": fmt}
    cols = [col]
    if template:
        enc["formatTemplate"], extra = template
        cols.append(extra)
    return {"widget": {"name": name, "queries": q("ds_kpi", cols),
                       "spec": {"version": 2, "widgetType": "counter", "encodings": {"value": enc},
                                "frame": {"showTitle": True, "title": title,
                                          "showDescription": True, "description": description}}},
            "position": pos(x, 3, 3, 3)}


def table(name, ds, title, columns, x, y, w, h, description=None):
    return {"widget": {"name": name, "queries": q(ds, [c[0] for c in columns]),
                       "spec": {"version": 2, "widgetType": "table",
                                "encodings": {"columns": [{"fieldName": c, "displayName": d, **({"format": f} if f else {})}
                                                          for c, d, f in columns]},
                                "frame": {"showTitle": True, "title": title,
                                          **({"showDescription": True, "description": description}
                                             if description else {})}}},
            "position": pos(x, y, w, h)}


STATUS = ("A candy is excluded from a bowl when its status is contains, varies or may_contain. "
          "Unknown means no matched product had an ingredient list.")

BAR_COLORS = [{"value": "1 No restriction", "color": GREY}] + [
    {"value": v, "color": ORANGE} for v in
    ["2 Peanut-free", "3 Nut-free", "4 Milk-free", "5 Gluten-free", "6 Free of all six"]]

LAYOUT = [
    text("title", ["# CandyOps: Allergy-Safe Halloween Candy"], 0, 0, 12, 1),
    text("subtitle", ["Popularity comes from 269,000 head-to-head votes in FiveThirtyEight's Candy Power Ranking. "
                      "Allergen status comes from 356,001 Open Food Facts products, cleaned and matched with dbt. "
                      "Each bowl contains the 10 most popular candies whose labels list none of the restricted "
                      "allergens."], 0, 1, 12, 2),
    counter("kpi-products", "Products analyzed", "products_scanned", CNT, 0,
            "Open Food Facts records loaded and cleaned"),
    counter("kpi-evidence", "Candies with allergen evidence", "candies_with_evidence", {"type": "number-plain"}, 3,
            "At least two matched products with ingredients",
            ("{{ @formatted }} of {{ ranked_candies }}", "ranked_candies")),
    counter("kpi-peanut", "Peanut-free bowl", "peanut_free_kept", PCT, 6,
            "Share of the unrestricted bowl's popularity retained"),
    counter("kpi-all-six", "Free of all six allergens", "all_six_kept", PCT, 9,
            "Peanut, tree nut, milk, gluten, soy and egg"),
    {"widget": {"name": "kept-by-restriction", "queries": q("ds_bowls", ["restriction_label", "popularity_kept"]),
                "spec": {"version": 3, "widgetType": "bar",
                         "encodings": {"x": {"fieldName": "restriction_label",
                                             "scale": {"type": "categorical", "sort": {"by": "alphabetical"}},
                                             "displayName": "Restriction"},
                                       "y": {"fieldName": "popularity_kept", "scale": {"type": "quantitative"},
                                             "displayName": "Popularity retained", "format": PCT},
                                       "color": {"fieldName": "restriction_label",
                                                 "scale": {"type": "categorical", "mappings": BAR_COLORS},
                                                 "displayName": "Restriction", "legend": {"hide": True}},
                                       "label": {"show": True}},
                         "frame": {"showTitle": True, "title": "Popularity retained by each restriction",
                                   "showDescription": True,
                                   "description": "Average win rate of each bowl compared with the unrestricted bowl"}}},
     "position": pos(0, 6, 6, 6)},
    table("bowls", "ds_bowls", "Recommended bowls", [("restriction_label", "Restriction", None),
                                                     ("candies_allowed", "Eligible candies", None),
                                                     ("popularity_kept", "Popularity retained", PCT),
                                                     ("bowl", "Top 10, most popular first", None)], 6, 6, 6, 6),
    table("candies", "ds_candies", "Allergen status of every ranked candy",
          [("popularity_rank", "Rank", None), ("candy", "Candy", None), ("win_rate", "Win rate", PCT),
           ("n_products", "Products matched", None), ("n_evidence", "With ingredients", None),
           ("evidence_scope", "Evidence source", None), ("peanut", "Peanut", None), ("tree_nut", "Tree nut", None),
           ("milk", "Milk", None), ("gluten", "Gluten", None), ("soy", "Soy", None), ("egg", "Egg", None),
           ("sugars_100g", "Sugar (g/100 g)", None)], 0, 12, 12, 9, STATUS),
    table("methods", "ds_methods", "Name matching compared with curated rules",
          [("method_label", "Method", None), ("candies_matched", "Candies matched", None),
           ("products_matched", "Products matched", None), ("us_products_matched", "US products", None),
           ("non_candy_products", "Non-candy matches", None)], 0, 21, 6, 6,
          "Matching on the name alone pulls in coffee creamer, ice cream and cereal"),
    table("quality", "ds_quality", "Data-cleaning results", [("metric", "Check", None), ("value", "Rows", CNT)],
          6, 21, 6, 6),
    table("changes", "ds_changes", "Is the 2017 answer still true? Labels edited since the daily feed started",
          [("candy", "Candy", None), ("allergen", "Allergen", None), ("status_2017", "2017 status", None),
           ("status_now", "Current status", None), ("evidence_2017", "2017 products", None),
           ("evidence_now", "Current products", None), ("comparison_label", "Comparison", None)], 0, 27, 12, 7,
          "From the Open Food Facts daily change feed, loaded incrementally. Only candies with at least two "
          "current products with ingredients are compared."),
    text("footer", ["Sources: Open Food Facts (ODbL) and FiveThirtyEight's Candy Power Ranking (MIT), 2017 "
                    "snapshots from Kaggle, plus the Open Food Facts daily change feed. Allergen status is parsed from crowdsourced ingredient lists, is not "
                    "medical advice, and may be out of date. Always check the package label. Each bowl and matching "
                    "method is logged to the MLflow experiment candyops-candy-bowls."], 0, 34, 12, 2),
]

DASH = {"datasets": DATASETS,
        "pages": [{"name": "overview", "displayName": "Candy and allergies", "layout": LAYOUT,
                   "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1"}],
        "uiSettings": {"theme": {
            "canvasBackgroundColor": {"light": "#FBF7F2", "dark": "#14101A"},
            "widgetBackgroundColor": {"light": "#FFFFFF", "dark": "#1E1726"},
            "widgetBorderColor": {"light": "#FFFFFF", "dark": "#1E1726"},
            "fontColor": {"light": "#1F1A24", "dark": "#F3EDE4"},
            "selectionColor": {"light": ORANGE, "dark": AMBER},
            "visualizationColors": [ORANGE, PURPLE, GREY, AMBER, LAVENDER, "#16A34A"],
            "widgetHeaderAlignment": "LEFT",
            "widgetCornerRadius": 12,
            "fontFamily": "Inter"}}}

if __name__ == "__main__":
    OUT.write_text(json.dumps(DASH, indent=2) + "\n")
    print(f"{OUT}: {len(DATASETS)} datasets, {len(LAYOUT)} widgets")
