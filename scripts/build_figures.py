"""Draw the blog figures from the Databricks gold tables into docs/figures/ (uses the databricks CLI's auth).

    uv run --with matplotlib python scripts/build_figures.py [--profile NAME] [--schema candyops]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from write_results import ROOT, WAREHOUSE, cli, query  # noqa: E402

OUT = ROOT / "docs" / "figures"
INK, MUTED, GRID, BG = "#1F1A24", "#6B6375", "#ECE8F0", "#FFFFFF"
ORANGE, PURPLE, GREY = "#C2410C", "#7C3AED", "#A8A29E"  # validated for a white surface
SEVERITY = {"contains": "#9A3412", "varies": "#EA580C", "may_contain": "#FB923C",
            "not_listed": "#F1EFEC", "unknown": "#FFFFFF"}
RESTRICTION_LABELS = {"no_restriction": "No restriction", "gluten_free": "Gluten-free", "peanut_free": "Peanut-free",
                      "nut_free": "Nut-free", "milk_free": "Milk-free", "free_of_all_six": "Free of all six"}
ALLERGENS = [("peanut", "Peanut"), ("tree_nut", "Tree nut"), ("milk", "Milk"), ("gluten", "Gluten"),
             ("soy", "Soy"), ("egg", "Egg")]
LISTED = "('contains', 'varies', 'may_contain')"

FONT = next((f for f in ["TeX Gyre Heros", "Liberation Sans", "DejaVu Sans"]
             if any(f == x.name for x in font_manager.fontManager.ttflist)), "DejaVu Sans")
plt.rcParams.update({"font.family": FONT, "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED,
                     "ytick.color": INK, "axes.edgecolor": GRID, "font.size": 11})


def figure(title: str, subtitle: str, height: float = 5.0):
    fig = plt.figure(figsize=(8, height), dpi=200, facecolor=BG)
    fig.text(0.04, 1 - 0.32 / height, title, fontsize=16, fontweight="bold", va="top")
    fig.text(0.04, 1 - 0.72 / height, subtitle, fontsize=10.5, color=MUTED, va="top")
    return fig


def tidy(ax, grid_axis="x"):
    for side in ax.spines.values():
        side.set_visible(False)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, name: str, source: str):
    fig.text(0.04, 0.025, f"Source: {source}. candyops, github.com/kidskoding/candyops", fontsize=8, color=MUTED)
    fig.savefig(OUT / name, facecolor=BG)
    plt.close(fig)
    print(OUT / name)


def allergens_vs_popularity(rows):
    for r in rows:
        r["n"], r["w"] = int(r["n_allergens"]), float(r["win_percent"])
    cols: dict[int, list] = {}
    for r in rows:
        cols.setdefault(r["n"], []).append(r)
    for n, members in cols.items():
        members.sort(key=lambda r: r["w"])
        for i, r in enumerate(members):
            r["x"] = n + (i % 4 - 1.5) * 0.11  # spread equal counts side by side so dots do not overlap
    fig = figure("The most popular candies list the most allergens",
                 f"Each dot is one of {len(rows)} candies with at least two labeled products. "
                 "Lines show the average win rate.", 5.6)
    ax = fig.add_axes([0.1, 0.14, 0.86, 0.66])
    for choc, color, label in [("true", ORANGE, "Chocolate"), ("false", PURPLE, "Not chocolate")]:
        pts = [r for r in rows if r["chocolate"] == choc]
        ax.scatter([r["x"] for r in pts], [r["w"] for r in pts], s=42, color=color, edgecolor=BG, linewidth=1,
                   zorder=3, label=label)
    for n, members in sorted(cols.items()):
        avg = sum(r["w"] for r in members) / len(members)
        ax.plot([n - 0.3, n + 0.3], [avg, avg], color=INK, linewidth=1.6, alpha=0.6, zorder=2)
    notes = {"Reese's Peanut Butter cup": ("Reese's Peanut Butter Cup", (1.4, 87)),
             "Snickers": ("Snickers", (5.3, 85)), "Twix": ("Twix", (4.0, 86)),
             "Skittles original": ("Skittles, the most popular\ncandy with none of the six", (0.3, 76))}
    for r in rows:
        if r["candy"] in notes:
            text, xy = notes[r["candy"]]
            ax.annotate(text, (r["x"], r["w"]), xytext=xy, fontsize=9, va="center",
                        arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.8})
    ax.set_xlim(-0.6, 6.6)
    ax.set_ylim(20, 92)
    ax.set_xticks(range(7))
    ax.set_yticks(range(20, 91, 10), [f"{v}%" for v in range(20, 91, 10)])
    ax.set_xlabel("Major allergens listed on the label (of 6, including may-contain warnings)")
    ax.set_ylabel("Win rate in head-to-head votes")
    tidy(ax, "y")
    ax.legend(loc="lower right", frameon=False, fontsize=9.5)
    save(fig, "fig1_allergens_vs_popularity.png", "FiveThirtyEight Candy Power Ranking, Open Food Facts (2017)")


def popularity_retained(bowls):
    bowls = sorted(bowls, key=lambda b: float(b["popularity_kept_pct"]))
    fig = figure("Every restriction costs popularity",
                 "Average win rate of each 10-candy bowl, as a share of the unrestricted bowl")
    ax = fig.add_axes([0.2, 0.12, 0.74, 0.66])
    labels = [RESTRICTION_LABELS[b["restriction"]] for b in bowls]
    values = [float(b["popularity_kept_pct"]) for b in bowls]
    colors = [GREY if b["restriction"] == "no_restriction" else ORANGE for b in bowls]
    ax.barh(labels, values, color=colors, height=0.62)
    for i, (v, b) in enumerate(zip(values, bowls, strict=True)):
        ax.text(v + 1, i, f"{v:.1f}%   {b['candies_allowed']} eligible candies", va="center", fontsize=9.5)
    ax.set_xlim(0, 135)
    ax.set_xticks(range(0, 101, 25), [f"{v}%" for v in range(0, 101, 25)])
    tidy(ax)
    save(fig, "fig2_popularity_retained.png", "candyops gold_bowl_summary")


def chocolate_share(mix):
    order = ["no_restriction", "gluten_free", "peanut_free", "nut_free", "milk_free", "free_of_all_six"][::-1]
    counts = {(m["restriction"], m["candy_type"]): int(m["candies"]) for m in mix}
    choc = [counts.get((r, "Chocolate"), 0) for r in order]
    other = [counts.get((r, "Not chocolate"), 0) for r in order]
    fig = figure("Chocolate disappears as restrictions are added",
                 "Chocolate and non-chocolate candies in each 10-candy bowl")
    ax = fig.add_axes([0.2, 0.12, 0.74, 0.62])
    labels = [RESTRICTION_LABELS[r] for r in order]
    ax.barh(labels, choc, color=ORANGE, height=0.62, label="Chocolate", edgecolor=BG, linewidth=1.5)
    ax.barh(labels, other, left=choc, color=PURPLE, height=0.62, label="Not chocolate", edgecolor=BG, linewidth=1.5)
    for i, (c, o) in enumerate(zip(choc, other, strict=True)):
        if c:
            ax.text(c / 2, i, str(c), ha="center", va="center", color=BG, fontsize=9.5, fontweight="bold")
        if o:
            ax.text(c + o / 2, i, str(o), ha="center", va="center", color=BG, fontsize=9.5, fontweight="bold")
    ax.set_xlim(0, 10)
    ax.set_xticks(range(0, 11, 2))
    tidy(ax)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False, fontsize=9.5)
    save(fig, "fig3_chocolate_share.png", "candyops gold_bowls and gold_candy_profile")


def sugar_by_bowl(bowls):
    bowls = sorted(bowls, key=lambda b: float(b["median_sugars_100g"]))
    fig = figure("Allergy-safe bowls contain more sugar",
                 "Median sugar per 100 g in each bowl. Safe bowls rely on fruit candy instead of chocolate.")
    ax = fig.add_axes([0.2, 0.17, 0.74, 0.61])
    labels = [RESTRICTION_LABELS[b["restriction"]] for b in bowls]
    values = [float(b["median_sugars_100g"]) for b in bowls]
    ax.barh(labels, values, color=[GREY if b["restriction"] == "no_restriction" else PURPLE for b in bowls],
            height=0.62)
    for i, v in enumerate(values):
        ax.text(v + 1, i, f"{v:.1f} g", va="center", fontsize=9.5)
    ax.set_xlim(0, 85)
    ax.set_xlabel("Grams of sugar per 100 g (median)")
    tidy(ax)
    save(fig, "fig4_sugar_by_bowl.png", "candyops gold_bowl_summary")


def allergen_heatmap(candies):
    fig = figure("Allergen status of the 20 most popular candies",
                 "From matched Open Food Facts labels. Unknown means no matched product had an ingredient list.", 8.2)
    ax = fig.add_axes([0.32, 0.1, 0.64, 0.76])
    short = {"contains": "contains", "varies": "varies", "may_contain": "may", "not_listed": "", "unknown": "?"}
    for row, c in enumerate(candies):
        for col, (key, _) in enumerate(ALLERGENS):
            status = c[key]
            ax.add_patch(plt.Rectangle((col, row), 0.94, 0.88, facecolor=SEVERITY[status],
                                       edgecolor=GRID if status == "unknown" else SEVERITY[status], linewidth=0.8,
                                       hatch="////" if status == "unknown" else None))
            ax.text(col + 0.47, row + 0.44, short[status], ha="center", va="center", fontsize=7.5,
                    color=BG if status in ("contains", "varies") else INK)
    ax.set_xlim(0, 6)
    ax.set_ylim(len(candies), 0)
    ax.set_xticks([i + 0.47 for i in range(6)], [label for _, label in ALLERGENS])
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.44 for i in range(len(candies))],
                  [f"{int(c['popularity_rank'])}. {c['candy']}" for c in candies], fontsize=9)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.tick_params(length=0)
    legend = [Patch(facecolor=SEVERITY[k], edgecolor=GRID, label=label) for k, label in
              [("contains", "Contains"), ("varies", "Varies by product"), ("may_contain", "May contain"),
               ("not_listed", "Not listed")]]
    legend.append(Patch(facecolor=BG, edgecolor=GRID, hatch="////", label="Unknown"))
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.62, 0.035), ncol=5, frameon=False, fontsize=8.5)
    save(fig, "fig5_allergen_heatmap.png", "candyops gold_candy_profile")


def matching_methods(methods):
    order = sorted(methods, key=lambda m: m["method"] != "naive")
    labels = ["Name only" if m["method"] == "naive" else "Curated rules" for m in order]
    fig = figure("Curated matching rules remove every false match",
                 "Matching on the name alone pulls in coffee creamer, ice cream and cereal")
    ax = fig.add_axes([0.1, 0.14, 0.86, 0.6])
    x = range(len(order))
    for offset, key, color, label in [(-0.2, "candies_matched", PURPLE, "Candies matched (of 83)"),
                                      (0.2, "non_candy_products", ORANGE, "Non-candy products matched")]:
        values = [int(m[key]) for m in order]
        ax.bar([i + offset for i in x], values, width=0.38, color=color, label=label)
        for i, v in zip(x, values, strict=True):
            ax.text(i + offset, v + 1.5, str(v), ha="center", fontsize=10)
    ax.set_xticks(list(x), labels, fontsize=11)
    ax.set_ylim(0, 95)
    tidy(ax, "y")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False, fontsize=9.5)
    save(fig, "fig6_matching_methods.png", "candyops gold_match_methods")


def label_changes(outcomes):
    order = ["Not enough current data", "Newly covered", "Unchanged", "Changed"]
    counts = {o["outcome"]: int(o["candies"]) for o in outcomes}
    compared = counts.get("Changed", 0) + counts.get("Unchanged", 0)
    fig = figure(f"{counts.get('Changed', 0)} of {compared} candies with current data changed allergen status",
                 "Each candy's 2017 status compared with products edited since the daily change feed started")
    ax = fig.add_axes([0.27, 0.17, 0.67, 0.61])
    colors = {"Changed": ORANGE, "Unchanged": PURPLE, "Newly covered": "#A78BFA", "Not enough current data": GREY}
    values = [counts.get(o, 0) for o in order]
    ax.barh(order, values, color=[colors[o] for o in order], height=0.62)
    for i, v in enumerate(values):
        ax.text(v + 0.8, i, str(v), va="center", fontsize=10)
    ax.set_xlabel("Candies")
    tidy(ax)
    save(fig, "fig7_label_changes.png", "candyops gold_label_changes")


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

    OUT.mkdir(parents=True, exist_ok=True)
    allergen_count = " + ".join(f"CAST({k} IN {LISTED} AS INT)" for k, _ in ALLERGENS)
    allergens_vs_popularity(q(f"SELECT candy, win_percent, CAST(chocolate AS STRING) AS chocolate, "
                              f"{allergen_count} AS n_allergens FROM {{s}}.gold_candy_profile WHERE n_evidence >= 2"))
    bowls = q("SELECT restriction, candies_allowed, popularity_kept_pct, median_sugars_100g FROM {s}.gold_bowl_summary")
    popularity_retained(bowls)
    chocolate_share(q("SELECT b.restriction, CASE WHEN p.chocolate THEN 'Chocolate' ELSE 'Not chocolate' END "
                      "AS candy_type, COUNT(*) AS candies FROM {s}.gold_bowls AS b "
                      "INNER JOIN {s}.gold_candy_profile AS p ON p.candy = b.candy GROUP BY 1, 2"))
    sugar_by_bowl(bowls)
    allergen_heatmap(q("SELECT popularity_rank, candy, peanut, tree_nut, milk, gluten, soy, egg "
                       "FROM {s}.gold_candy_profile WHERE popularity_rank <= 20 ORDER BY popularity_rank"))
    matching_methods(q("SELECT method, candies_matched, non_candy_products FROM {s}.gold_match_methods"))
    label_changes(q("SELECT outcome, COUNT(*) AS candies FROM (SELECT candy, CASE "
                    "WHEN MAX(CASE WHEN comparison = 'changed' THEN 1 ELSE 0 END) = 1 THEN 'Changed' "
                    "WHEN MAX(CASE WHEN comparison = 'unchanged' THEN 1 ELSE 0 END) = 1 THEN 'Unchanged' "
                    "WHEN MAX(CASE WHEN comparison = 'newly_covered' THEN 1 ELSE 0 END) = 1 THEN 'Newly covered' "
                    "ELSE 'Not enough current data' END AS outcome FROM {s}.gold_label_changes GROUP BY candy) "
                    "GROUP BY outcome"))


if __name__ == "__main__":
    main()
