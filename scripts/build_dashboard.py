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
  (SELECT popularity_kept_pct / 100 FROM gold_bowl_summary WHERE restriction = 'free_of_all_six') AS all_six_kept,
  (SELECT COUNT(DISTINCT candy) FROM gold_label_changes WHERE comparison = 'changed') AS candies_changed,
  (SELECT COUNT(DISTINCT candy) FROM gold_label_changes WHERE comparison IN ('changed', 'unchanged')) AS candies_compared
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
    {"name": "ds_bowl_mix", "displayName": "Chocolate share of each bowl", "queryLines": ql(f"""
SELECT
  {LABEL.replace("restriction", "b.restriction", 1)} AS restriction_label,
  CASE WHEN p.chocolate THEN 'Chocolate' ELSE 'Non-chocolate' END AS candy_type,
  COUNT(*) AS candies
FROM gold_bowls AS b
INNER JOIN gold_candy_profile AS p ON p.candy = b.candy
GROUP BY 1, 2
ORDER BY 1, 2""")},
    {"name": "ds_heatmap", "displayName": "Allergen status of the 20 most popular candies", "queryLines": ql("""
SELECT
  CONCAT(LPAD(CAST(popularity_rank AS STRING), 2, '0'), '  ', candy) AS candy_label,
  allergen,
  CASE status WHEN 'contains' THEN 3 WHEN 'varies' THEN 2 WHEN 'may_contain' THEN 1 WHEN 'not_listed' THEN 0 END
    AS severity
FROM (SELECT popularity_rank, candy, peanut, tree_nut, milk, gluten, soy, egg
      FROM gold_candy_profile WHERE popularity_rank <= 20)
UNPIVOT (status FOR allergen IN (peanut AS `Peanut`, tree_nut AS `Tree nut`, milk AS `Milk`, gluten AS `Gluten`,
                                 soy AS `Soy`, egg AS `Egg`))
ORDER BY candy_label""")},
    {"name": "ds_change_outcomes", "displayName": "2017 versus now, per candy", "queryLines": ql("""
SELECT outcome, COUNT(*) AS candies
FROM (
  SELECT
    candy,
    CASE
      WHEN MAX(CASE WHEN comparison = 'changed' THEN 1 ELSE 0 END) = 1 THEN 'Changed'
      WHEN MAX(CASE WHEN comparison = 'unchanged' THEN 1 ELSE 0 END) = 1 THEN 'Unchanged'
      WHEN MAX(CASE WHEN comparison = 'newly_covered' THEN 1 ELSE 0 END) = 1 THEN 'Newly covered'
      ELSE 'Not enough current data'
    END AS outcome
  FROM gold_label_changes
  GROUP BY candy
)
GROUP BY outcome""")},
    {"name": "ds_changes_by_allergen", "displayName": "Changed statuses by allergen", "queryLines": ql("""
SELECT
  CASE allergen WHEN 'peanut' THEN 'Peanut' WHEN 'tree_nut' THEN 'Tree nut' WHEN 'milk' THEN 'Milk'
    WHEN 'gluten' THEN 'Gluten' WHEN 'soy' THEN 'Soy' WHEN 'egg' THEN 'Egg' END AS allergen_label,
  COUNT(*) AS changes
FROM gold_label_changes
WHERE comparison = 'changed'
GROUP BY 1
ORDER BY changes DESC""")},
    {"name": "ds_allergen_popularity", "displayName": "Popularity versus allergens listed", "queryLines": ql("""
SELECT
  candy,
  win_percent / 100 AS win_rate,
  n_allergens,
  -- spread candies with the same count side by side so the dots do not overlap
  n_allergens + ((ROW_NUMBER() OVER (PARTITION BY n_allergens ORDER BY win_percent) % 4) - 1.5) * 0.11
    AS allergens_listed,
  CASE WHEN chocolate THEN 'Chocolate' ELSE 'Not chocolate' END AS candy_type
FROM (
  SELECT
    candy,
    win_percent,
    chocolate,
    CAST(peanut IN ('contains', 'varies', 'may_contain') AS INT)
      + CAST(tree_nut IN ('contains', 'varies', 'may_contain') AS INT)
      + CAST(milk IN ('contains', 'varies', 'may_contain') AS INT)
      + CAST(gluten IN ('contains', 'varies', 'may_contain') AS INT)
      + CAST(soy IN ('contains', 'varies', 'may_contain') AS INT)
      + CAST(egg IN ('contains', 'varies', 'may_contain') AS INT) AS n_allergens
  FROM gold_candy_profile
  WHERE n_evidence >= 2
)
ORDER BY n_allergens, win_rate""")},
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

RESTRICTIONS = ["1 No restriction", "2 Peanut-free", "3 Nut-free", "4 Milk-free", "5 Gluten-free",
                "6 Free of all six"]
BAR_COLORS = [{"value": RESTRICTIONS[0], "color": GREY}] + [{"value": v, "color": ORANGE} for v in RESTRICTIONS[1:]]
SUGAR_COLORS = [{"value": RESTRICTIONS[0], "color": GREY}] + [{"value": v, "color": LAVENDER} for v in RESTRICTIONS[1:]]
OUTCOMES = ["Changed", "Unchanged", "Newly covered", "Not enough current data"]
NO_LEGEND = {"hide": True}


def frame(title, description=None):
    return {"showTitle": True, "title": title, **({"showDescription": True, "description": description}
                                                   if description else {})}


def bar(name, ds, x, y, title, description, position, color=None, mark=None, horizontal=False):
    """x and y are (field, display name, extra encoding keys); color is an encoding dict or None."""
    fields = [x[0]] + ([f[0] for f in y] if isinstance(y, list) else [y[0]]) + ([color["fieldName"]] if color and
                                                                                color["fieldName"] != x[0] else [])
    cat = {"fieldName": x[0], "displayName": x[1], "scale": {"type": "categorical", **x[2]}}
    if isinstance(y, list):
        val = {"scale": {"type": "quantitative"}, "fields": [{"fieldName": f, "displayName": d} for f, d in y]}
    else:
        val = {"fieldName": y[0], "displayName": y[1], "scale": {"type": "quantitative"}, **y[2]}
    enc = {"y": cat, "x": val} if horizontal else {"x": cat, "y": val}
    if color:
        enc["color"] = color
    enc["label"] = {"show": True}
    spec = {"version": 3, "widgetType": "bar", "encodings": enc, "frame": frame(title, description)}
    if mark:
        spec["mark"] = mark
    return {"widget": {"name": name, "queries": q(ds, list(dict.fromkeys(fields))), "spec": spec},
            "position": pos(*position)}


def by_restriction(colors):
    return {"fieldName": "restriction_label", "displayName": "Restriction", "legend": NO_LEGEND,
            "scale": {"type": "categorical", "mappings": colors}}


ORDERED = {"sort": {"by": "custom-order", "orderedValues": RESTRICTIONS}}

LAYOUT = [
    text("title", ["# candyops: Allergy-Safe Halloween Candy"], 0, 0, 12, 1),
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
    counter("kpi-changed", "Allergen labels changed since 2017", "candies_changed", {"type": "number-plain"}, 9,
            "Candies with current data whose status changed",
            ("{{ @formatted }} of {{ candies_compared }}", "candies_compared")),

    {"widget": {"name": "allergens-vs-popularity",
                "queries": q("ds_allergen_popularity", ["allergens_listed", "win_rate", "candy_type"]),
                "spec": {"version": 3, "widgetType": "scatter",
                         "encodings": {
                             "x": {"fieldName": "allergens_listed", "scale": {"type": "quantitative"},
                                   "displayName": "Major allergens listed on the label (of 6)",
                                   "format": {"type": "number", "decimalPlaces": {"type": "exact", "places": 0}}},
                             "y": {"fieldName": "win_rate", "scale": {"type": "quantitative"},
                                   "displayName": "Win rate in head-to-head votes", "format": PCT},
                             "color": {"fieldName": "candy_type", "displayName": "Candy type",
                                       "scale": {"type": "categorical", "mappings": [
                                           {"value": "Chocolate", "color": "#EA580C"},
                                           {"value": "Not chocolate", "color": "#8B5CF6"}]}}},
                         "frame": frame("The candy kids love most is the candy allergic kids can't eat",
                                        "Each dot is one of 59 candies with at least two labeled products. "
                                        "Listed includes may-contain warnings.")}},
     "position": pos(0, 6, 12, 8)},

    bar("kept-by-restriction", "ds_bowls", ("restriction_label", "Restriction", ORDERED),
        ("popularity_kept", "Popularity retained", {"format": PCT}),
        "Popularity retained by each restriction",
        "Average win rate of each bowl compared with the unrestricted bowl", (0, 14, 6, 6),
        color=by_restriction(BAR_COLORS)),
    bar("chocolate-mix", "ds_bowl_mix", ("restriction_label", "Restriction", ORDERED),
        ("candies", "Candies in the bowl", {}),
        "Chocolate disappears as restrictions are added",
        "Chocolate and non-chocolate candies in each 10-candy bowl", (6, 14, 6, 6),
        color={"fieldName": "candy_type", "displayName": "Candy type", "scale": {"type": "categorical", "mappings": [
            {"value": "Chocolate", "color": "#9A5B2E"}, {"value": "Non-chocolate", "color": ORANGE}]}}),

    bar("sugar-by-bowl", "ds_bowls", ("restriction_label", "Restriction", ORDERED),
        ("median_sugars_100g", "Median sugar (g per 100 g)", {}),
        "Allergy-safe bowls contain more sugar",
        "Median sugar per 100 g in each bowl. Safe bowls rely on fruit candy instead of chocolate.", (0, 20, 6, 6),
        color=by_restriction(SUGAR_COLORS)),
    bar("matching-methods", "ds_methods", ("method_label", "Method", {}),
        [("candies_matched", "Candies matched"), ("non_candy_products", "Non-candy products matched")],
        "Curated rules remove every false match",
        "Matching on the name alone pulls in coffee creamer, ice cream and cereal", (6, 20, 6, 6),
        mark={"layout": "group"}),

    {"widget": {"name": "allergen-heatmap", "queries": q("ds_heatmap", ["allergen", "candy_label", "severity"]),
                "spec": {"version": 3, "widgetType": "heatmap",
                         "encodings": {
                             "x": {"fieldName": "allergen", "displayName": "Allergen", "axis": {"hideTitle": True},
                                   "scale": {"type": "categorical", "sort": {"by": "custom-order", "orderedValues":
                                             ["Peanut", "Tree nut", "Milk", "Gluten", "Soy", "Egg"]}}},
                             "y": {"fieldName": "candy_label", "displayName": "Candy", "axis": {"hideTitle": True},
                                   "scale": {"type": "categorical", "sort": {"by": "alphabetical"}}},
                             "color": {"fieldName": "severity", "displayName": "Status",
                                       "scale": {"type": "quantitative", "colorRamp": {
                                           "mode": "custom-sequential",
                                           "colors": {"start": "#2A2133", "end": ORANGE}}}}},
                         "frame": frame("Allergen status of the 20 most popular candies",
                                        "0 not listed, 1 may contain, 2 varies by product, 3 contains. "
                                        "Blank cells have no matched ingredient list.")}},
     "position": pos(0, 26, 12, 9)},

    bar("change-outcomes", "ds_change_outcomes", ("outcome", "Outcome", {"sort": {"by": "custom-order",
                                                                               "orderedValues": OUTCOMES}}),
        ("candies", "Candies", {}),
        "Is the 2017 answer still true?",
        "Each candy's 2017 allergen status compared with products edited since the daily change feed started",
        (0, 35, 6, 6),
        color={"fieldName": "outcome", "displayName": "Outcome", "legend": NO_LEGEND,
               "scale": {"type": "categorical", "mappings": [
                   {"value": "Changed", "color": ORANGE}, {"value": "Unchanged", "color": PURPLE},
                   {"value": "Newly covered", "color": AMBER}, {"value": "Not enough current data", "color": GREY}]}}),
    bar("changes-by-allergen", "ds_changes_by_allergen", ("allergen_label", "Allergen", {"sort": {"by": "custom-order", "orderedValues":
                                                                ["Peanut", "Tree nut", "Egg", "Soy", "Gluten", "Milk"]}}),
        ("changes", "Changed statuses", {}),
        "Which allergen statuses changed",
        "Candy and allergen pairs whose status differs between 2017 and current labels", (6, 35, 6, 6),
        color={"fieldName": "allergen_label", "displayName": "Allergen", "legend": NO_LEGEND,
               "scale": {"type": "categorical", "mappings": [
                   {"value": a, "color": ORANGE} for a in ["Peanut", "Tree nut", "Milk", "Gluten", "Soy", "Egg"]]}}),

    table("changes", "ds_changes", "Allergen statuses that changed since 2017",
          [("candy", "Candy", None), ("allergen", "Allergen", None), ("status_2017", "2017 status", None),
           ("status_now", "Current status", None), ("evidence_2017", "2017 products", None),
           ("evidence_now", "Current products", None), ("comparison_label", "Comparison", None)], 0, 41, 12, 6,
          "From the Open Food Facts daily change feed, loaded incrementally. Only candies with at least two "
          "current products with ingredients are compared."),
    table("bowls", "ds_bowls", "Recommended bowls", [("restriction_label", "Restriction", None),
                                                     ("candies_allowed", "Eligible candies", None),
                                                     ("popularity_kept", "Popularity retained", PCT),
                                                     ("bowl", "Top 10, most popular first", None)], 0, 47, 12, 5),
    table("candies", "ds_candies", "Evidence behind every ranked candy",
          [("popularity_rank", "Rank", None), ("candy", "Candy", None), ("win_rate", "Win rate", PCT),
           ("n_evidence", "Labels with ingredients", None), ("evidence_scope", "Evidence source", None),
           ("sugars_100g", "Sugar (g/100 g)", None)], 0, 52, 12, 8, STATUS),
    table("quality", "ds_quality", "Data-cleaning results", [("metric", "Check", None), ("value", "Rows", CNT)],
          0, 60, 12, 5),
    text("footer", ["Sources: Open Food Facts (ODbL) and FiveThirtyEight's Candy Power Ranking (MIT), 2017 "
                    "snapshots from Kaggle, plus the Open Food Facts daily change feed. Allergen status is parsed "
                    "from crowdsourced ingredient lists, is not medical advice, and may be out of date. Always check "
                    "the package label. Each bowl and matching method is logged to the MLflow experiment "
                    "candyops-candy-bowls."], 0, 65, 12, 2),
]

# Each section pairs a chart with the table or notes that explain it, instead of stacking every table at the end.
# shortcut: these numbers are typed in, not queried; rerun scripts/build_figures.py and update them if the data changes.
FINDINGS = text("findings", [
    "## What the data shows\n", "\n",
    "- **9 of the 10** most popular candies with label data list at least 3 of the 6 major allergens.\n",
    "- Candies with none average a **45%** win rate. Candies with 5 or more average **66%**.\n",
    "- **Skittles** is the most popular candy with none of the six.\n",
    "- Chocolate drives the pattern: it almost always contains milk and soy, so allergy-safe bowls are fruit candy.\n",
], 0, 0, 0, 0)
SECTIONS = [
    text("section-bowls", ["## The bowls: what an allergy costs"], 0, 0, 0, 0),
    text("section-candies", ["## Every candy: allergen status and evidence"], 0, 0, 0, 0),
    text("section-changes", ["## Is the 2017 answer still true?"], 0, 0, 0, 0),
    text("section-cleaning", ["## How the data was cleaned and matched"], 0, 0, 0, 0),
]
POSITIONS = {
    "title": (0, 0, 12, 1), "subtitle": (0, 1, 12, 2),
    "kpi-products": (0, 3, 3, 3), "kpi-evidence": (3, 3, 3, 3), "kpi-peanut": (6, 3, 3, 3), "kpi-changed": (9, 3, 3, 3),
    "allergens-vs-popularity": (0, 6, 8, 9), "findings": (8, 6, 4, 9),
    "section-bowls": (0, 15, 12, 1),
    "kept-by-restriction": (0, 16, 5, 6), "bowls": (5, 16, 7, 6),
    "chocolate-mix": (0, 22, 6, 6), "sugar-by-bowl": (6, 22, 6, 6),
    "section-candies": (0, 28, 12, 1),
    "allergen-heatmap": (0, 29, 7, 10), "candies": (7, 29, 5, 10),
    "section-changes": (0, 39, 12, 1),
    "change-outcomes": (0, 40, 4, 7), "changes": (4, 40, 8, 7),
    "changes-by-allergen": (0, 47, 4, 6),
    "section-cleaning": (4, 47, 8, 1),
    "matching-methods": (4, 48, 4, 5), "quality": (8, 48, 4, 5),
    "footer": (0, 53, 12, 2),
}
LAYOUT = LAYOUT + [FINDINGS] + SECTIONS
for item in LAYOUT:
    item["position"] = pos(*POSITIONS[item["widget"]["name"]])
LAYOUT.sort(key=lambda item: (item["position"]["y"], item["position"]["x"]))

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
