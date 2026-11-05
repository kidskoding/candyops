"""The gold-table queries behind every chart, shared by build_figures.py and export_chart_data.py."""

from __future__ import annotations

from collections.abc import Callable

ALLERGENS = [("peanut", "Peanut"), ("tree_nut", "Tree nut"), ("milk", "Milk"), ("gluten", "Gluten"),
             ("soy", "Soy"), ("egg", "Egg")]
LISTED = "('contains', 'varies', 'may_contain')"


def load(q: Callable[[str], list[dict]]) -> dict[str, list[dict]]:
    """Run every chart query; q formats {s} with the schema and returns rows as dicts."""
    allergen_count = " + ".join(f"CAST({k} IN {LISTED} AS INT)" for k, _ in ALLERGENS)
    return {
        "candies": q(f"SELECT candy, win_percent, CAST(chocolate AS STRING) AS chocolate, {allergen_count} "
                     "AS n_allergens FROM {s}.gold_candy_profile WHERE n_evidence >= 2"),
        "bowls": q("SELECT restriction, candies_allowed, popularity_kept_pct, median_sugars_100g, bowl "
                   "FROM {s}.gold_bowl_summary"),
        "bowl_mix": q("SELECT b.restriction, CASE WHEN p.chocolate THEN 'Chocolate' ELSE 'Not chocolate' END "
                      "AS candy_type, COUNT(*) AS candies, array_join(collect_list(b.candy), ', ') AS candy_list "
                      "FROM {s}.gold_bowls AS b INNER JOIN {s}.gold_candy_profile AS p ON p.candy = b.candy "
                      "GROUP BY 1, 2"),
        "heatmap": q("SELECT popularity_rank, candy, peanut, tree_nut, milk, gluten, soy, egg "
                     "FROM {s}.gold_candy_profile WHERE popularity_rank <= 20 ORDER BY popularity_rank"),
        "methods": q("SELECT method, candies_matched, products_matched, non_candy_products "
                     "FROM {s}.gold_match_methods"),
        "outcomes": q("SELECT outcome, COUNT(*) AS candies, array_join(sort_array(collect_list(candy)), ', ') "
                      "AS candy_list FROM (SELECT candy, CASE "
                      "WHEN MAX(CASE WHEN comparison = 'changed' THEN 1 ELSE 0 END) = 1 THEN 'Changed' "
                      "WHEN MAX(CASE WHEN comparison = 'unchanged' THEN 1 ELSE 0 END) = 1 THEN 'Unchanged' "
                      "WHEN MAX(CASE WHEN comparison = 'newly_covered' THEN 1 ELSE 0 END) = 1 THEN 'Newly covered' "
                      "ELSE 'Not enough current data' END AS outcome FROM {s}.gold_label_changes GROUP BY candy) "
                      "GROUP BY outcome"),
        "warning_cost": q("SELECT * FROM {s}.gold_warning_cost"),
        "swaps": q("SELECT * FROM {s}.gold_safe_swaps"),
        "safe_by_allergy": q("SELECT p.candy, p.win_percent, collect_list(a.allergen) AS safe_for "
                             "FROM {s}.gold_candy_profile AS p LEFT JOIN {s}.gold_allergy_safe_candies AS a "
                             "ON a.candy = p.candy GROUP BY p.candy, p.win_percent"),
        "street": q("SELECT candy, win_percent, to_json(safe_for) AS safe_for, in_regular_bowl "
                    "FROM {s}.gold_street_bowl"),
    }
