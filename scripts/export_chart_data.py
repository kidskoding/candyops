"""Export the blog's chart data, with hover text, from the Databricks gold tables to one JSON file.

    uv run python scripts/export_chart_data.py --out <portfolio post folder>/charts.json [--profile NAME]

The portfolio's Astro chart components read this file at build time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chart_queries import load  # noqa: E402
from write_results import WAREHOUSE, cli, query  # noqa: E402

LABELS = {"no_restriction": "No restriction", "gluten_free": "Gluten-free", "peanut_free": "Peanut-free",
          "nut_free": "Nut-free", "milk_free": "Milk-free", "free_of_all_six": "Free of all six"}
ORDER = ["no_restriction", "gluten_free", "peanut_free", "nut_free", "milk_free", "free_of_all_six"]
ALLERGY_NAMES = {"peanut": "peanut", "milk": "milk", "tree_nut": "tree nut"}


def pct(v: float) -> str:
    return f"{float(v):.1f}%"


def allergens_vs_popularity(rows):
    rows = sorted(rows, key=lambda r: (int(r["n_allergens"]), float(r["win_percent"])))
    groups: dict[int, list] = {}
    for r in rows:
        groups.setdefault(int(r["n_allergens"]), []).append(r)
    # label text and its offset from the dot in chart pixels, placed in empty space with a leader line
    callouts = {"Reese's Peanut Butter cup": {"text": "Reese's Peanut Butter Cup", "dx": -46, "dy": -26},
                "Twix": {"text": "Twix", "dx": -40, "dy": -30},
                "Snickers": {"text": "Snickers", "dx": -34, "dy": -40},
                "Skittles original": {"text": "Skittles: most popular with none of the six", "dx": 30,
                                      "dy": -72}}
    points, averages = [], []
    for n, members in sorted(groups.items()):
        for i, r in enumerate(members):
            choc = r["chocolate"] == "true"
            points.append({
                "x": n + (i % 4 - 1.5) * 0.11,  # spread equal counts side by side so dots do not overlap
                "y": round(float(r["win_percent"]), 1),
                "color": "red" if choc else "aqua",
                "label": callouts.get(r["candy"]),
                "tip": f"{r['candy']}\n{pct(r['win_percent'])} win rate\n{n} of 6 allergens listed\n"
                       f"{'Chocolate' if choc else 'Not chocolate'}",
            })
        avg = sum(float(r["win_percent"]) for r in members) / len(members)
        averages.append({"x": n, "y": round(avg, 1),
                         "tip": f"{n} allergens listed\nAverage win rate {pct(avg)} across {len(members)} candies"})
    return {"points": points, "averages": averages}


def popularity(bowls):
    by = {b["restriction"]: b for b in bowls}
    return {"rows": [{
        "label": LABELS[r],
        "bars": [{"value": float(by[r]["popularity_kept_pct"]), "color": "gray" if r == "no_restriction" else "red",
                  "tip": f"{LABELS[r]} bowl\n{pct(by[r]['popularity_kept_pct'])} popularity score\n"
                         f"{by[r]['candies_allowed']} eligible candies\nBowl: {by[r]['bowl']}"}],
        "valueText": pct(by[r]["popularity_kept_pct"]),
        "note": f"{by[r]['candies_allowed']} eligible candies",
    } for r in ORDER]}


def chocolate(mix):
    counts = {(m["restriction"], m["candy_type"]): m for m in mix}
    rows = []
    for r in ORDER:
        bars = []
        for kind, color in [("Chocolate", "red"), ("Not chocolate", "aqua")]:
            m = counts.get((r, kind))
            if m:
                bars.append({"value": int(m["candies"]), "color": color, "text": str(m["candies"]),
                             "tip": f"{LABELS[r]} bowl\n{kind}: {m['candies']} of 10 candies\n{m['candy_list']}"})
        rows.append({"label": LABELS[r], "bars": bars})
    return {"rows": rows}


def sugar(bowls):
    rows = sorted(bowls, key=lambda b: -float(b["median_sugars_100g"]))
    return {"rows": [{
        "label": LABELS[b["restriction"]],
        "bars": [{"value": float(b["median_sugars_100g"]),
                  "color": "gray" if b["restriction"] == "no_restriction" else "aqua",
                  "tip": f"{LABELS[b['restriction']]} bowl\nMedian {float(b['median_sugars_100g']):.1f} g of sugar "
                         f"per 100 g"}],
        "valueText": f"{float(b['median_sugars_100g']):.1f} g",
    } for b in rows]}


def matching(methods):
    rows = sorted(methods, key=lambda m: m["method"] != "naive")
    out = []
    for m in rows:
        name = "Name only" if m["method"] == "naive" else "Curated rules"
        out.append({"label": name, "bars": [
            {"value": int(m["candies_matched"]), "color": "aqua", "text": str(m["candies_matched"]),
             "tip": f"{name}\n{m['candies_matched']} of 83 candies matched\n{m['products_matched']} products matched"},
            {"value": int(m["non_candy_products"]), "color": "red", "text": str(m["non_candy_products"]),
             "tip": f"{name}\n{m['non_candy_products']} matched products that are not candy"},
        ]})
    return {"rows": out}


def label_changes(outcomes):
    order = [("Changed", "red"), ("Unchanged", "aqua"), ("Newly covered", "fg2"), ("Not enough current data", "gray")]
    by = {o["outcome"]: o for o in outcomes}
    rows = []
    for name, color in order:
        o = by.get(name)
        if not o:
            continue
        listing = "" if name == "Not enough current data" else f"\n{o['candy_list']}"
        rows.append({"label": name, "bars": [{"value": int(o["candies"]), "color": color,
                                              "tip": f"{name}: {o['candies']} candies{listing}"}],
                     "valueText": str(o["candies"])})
    return {"rows": rows}


def warning_cost(rows):
    rows = sorted(rows, key=lambda r: -float(r["popularity_kept_strict_pct"]))
    out = []
    for r in rows:
        a, b = float(r["popularity_kept_strict_pct"]), float(r["popularity_kept_with_warnings_pct"])
        added = r.get("added_candies") or "none"
        out.append({
            "label": LABELS[r["restriction"]],
            "a": {"value": a, "tip": f"{LABELS[r['restriction']]}, warnings exclude\n{pct(a)} popularity score"},
            "b": {"value": b, "tip": f"{LABELS[r['restriction']]}, warnings accepted\n{pct(b)} popularity score\n"
                                     f"Candies added: {added}"},
            "note": f"+{b - a:.1f}" if b > a else "no change",
        })
    return {"rows": out}


SWAP_VIEWS = ["peanut_free", "nut_free", "milk_free", "gluten_free"]


def swaps(all_rows):
    return {"views": [{"key": r, "label": LABELS[r], "rows": swap_rows([x for x in all_rows if x["restriction"] == r])}
                      for r in SWAP_VIEWS]}


def simulator(rows):
    """Every ranked candy with its win rate and the allergies it is safe for, for the in-browser street bowl."""
    out = []
    for r in sorted(rows, key=lambda r: -float(r["win_percent"])):
        safe = json.loads(r["safe_for"]) if isinstance(r["safe_for"], str) else list(r["safe_for"] or [])
        out.append({"candy": r["candy"], "win": round(float(r["win_percent"]), 2), "safe": sorted(safe)})
    return {"candies": out}


def swap_rows(rows):
    rows = sorted(rows, key=lambda r: int(r["favorite_rank"]))
    return [{
        "label": r["favorite"],
        "a": {"value": float(r["swap_win_percent"]), "label": r["swap"],
              "tip": f"{r['swap']}\n{pct(r['swap_win_percent'])} win rate\n"
                     f"Shared traits: {r['shared_traits'] or 'none'}"},
        "b": {"value": float(r["favorite_win_percent"]),
              "tip": f"{r['favorite']}\n{pct(r['favorite_win_percent'])} win rate"},
    } for r in rows]


def street(rows):
    rows = sorted(rows, key=lambda r: -float(r["win_percent"]))
    out = []
    for r in rows:
        safe = json.loads(r["safe_for"]) if isinstance(r["safe_for"], str) else list(r["safe_for"] or [])
        safe_text = ", ".join(ALLERGY_NAMES[a] for a in safe)
        detail = f"Safe for {safe_text} allergies\nReplaces Butterfinger" if safe else "Not safe for any of the three"
        tip = f"{r['candy']}\n{pct(r['win_percent'])} win rate\n{detail}"
        out.append({"label": r["candy"], "bars": [{"value": float(r["win_percent"]),
                                                   "color": "aqua" if safe else "gray", "tip": tip}],
                    "valueText": pct(r["win_percent"]), "note": "allergy-safe, replaces Butterfinger" if safe else ""})
    return {"rows": out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile")
    ap.add_argument("--catalog", default="workspace")
    ap.add_argument("--schema", default="candyops")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    wh = next(w["id"] for w in cli(["warehouses", "list"], a.profile) if w["name"] == WAREHOUSE)
    s = f"`{a.catalog}`.`{a.schema}`"
    d = load(lambda sql: query(sql.format(s=s), wh, a.profile))
    charts = {
        "allergensVsPopularity": allergens_vs_popularity(d["candies"]),
        "popularity": popularity(d["bowls"]),
        "chocolate": chocolate(d["bowl_mix"]),
        "sugar": sugar(d["bowls"]),
        "matching": matching(d["methods"]),
        "labelChanges": label_changes(d["outcomes"]),
        "warningCost": warning_cost(d["warning_cost"]),
        "swaps": swaps(d["swaps"]),
        "street": street(d["street"]),
        "simulator": simulator(d["safe_by_allergy"]),
    }
    a.out.write_text(json.dumps(charts, indent=2) + "\n")
    print(f"{a.out}: {len(charts)} charts from {a.catalog}.{a.schema}")


if __name__ == "__main__":
    main()
