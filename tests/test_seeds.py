"""The dbt seeds hold the regex rules; these tests pin their behaviour on real Open Food Facts product text.

Patterns stay within the regex subset that Python and Java (Spark rlike) read the same way.
"""

import re

import pytest

from candyops.config import RANKING_ROWS


def matched_candies(text, aliases, rules):
    """Same condition as dbt/models/silver/silver_candy_matches.sql."""
    if re.search(rules["not_candy"], text):
        return set()
    return {a["competitorname"] for a in aliases
            if re.search(a["include"], text) and not (a["exclude"] and re.search(a["exclude"], text))}


def contains(allergen, text, terms):
    t = terms[allergen]
    return bool(re.search(t["contains_regex"], re.sub(t["ignore_regex"] or "(?!)", " ", text)))


def test_every_rule_compiles_and_names_are_unique(aliases, terms, rules):
    names = [a["competitorname"] for a in aliases]
    assert len(names) == len(set(names)) == RANKING_ROWS - 2  # the two coins have no rule
    patterns = [a["include"] for a in aliases] + [a["exclude"] for a in aliases if a["exclude"]]
    patterns += [t[k] for t in terms.values() for k in ("contains_regex", "ignore_regex") if t[k]]
    for pattern in patterns + list(rules.values()):
        re.compile(pattern)


@pytest.mark.parametrize("text, expected", [
    ("kitkat || kitkat", {"Kit Kat"}),
    ("mike and ike || mike and ike", {"Mike & Ike"}),
    ("classic candy corn || brachs, ferrara candy company", {"Candy Corn"}),
    ("candy rolls || smarties", {"Smarties candy"}),
    ("smarties || nestle", {"Nestle Smarties"}),
    ("snickers minis || mars", {"Snickers"}),
    ("m&ms || m&ms", {"M&M's"}),
    ("peanut m&ms || mars", {"Peanut M&Ms"}),
    ("hersheys milk chocolate || hersheys", {"Hershey's Milk Chocolate"}),
])
def test_rules_link_real_product_names(text, expected, aliases, rules):
    assert matched_candies(text, aliases, rules) == expected


@pytest.mark.parametrize("text", [
    "almond joy, gourmet coffee creamer, milk chocolate almond || international delight,  dean foods company",
    "hersheys milk chocolate with almonds || hersheys",
    "snickers almond || mars",
    "transformer hersheys ice cream blast ice cream bar || autobut",
    "scrambled pork, wild fennel and barolo wine pasta sauce || hemis fares",
    # derived products once made Butterfinger look peanut-free
    "crispy marshmallow squares made with nestle butterfinger || ",
    "gourmet butterfinger caramel apple || ",
])
def test_rules_reject_lookalikes(text, aliases, rules):
    assert matched_candies(text, aliases, rules) == set()


@pytest.mark.parametrize("allergen, text, expected", [
    ("milk", "sugar, cocoa butter, chocolate, soy lecithin", False),
    ("milk", "sugar, milk chocolate (sugar, cocoa butter, skim milk)", True),
    ("milk", "peanut butter, sugar", False),
    ("peanut", "peanut butter, sugar", True),
    ("tree_nut", "peanuts, coconut oil, sugar", False),
    ("tree_nut", "sugar, hazelnuts, cocoa", True),
    ("gluten", "corn syrup, maltodextrin", False),
    ("gluten", "wheat flour, barley malt", True),
    ("soy", "soy lecithin", True),
    ("egg", "egg whites", True),
    ("milk", "sucre, beurre de cacao, lait entier en poudre", True),
])
def test_allergen_terms(allergen, text, expected, terms):
    assert contains(allergen, text, terms) is expected


def test_may_contain_warning_is_split_off(rules, terms):
    body, *tail = re.split(rules["may_contain"], "sugar, cocoa. may contain peanuts and milk", maxsplit=1)
    assert not contains("peanut", body, terms)
    assert contains("peanut", tail[-1], terms)


def test_negations_are_removed(rules, terms):
    text = re.sub(rules["negation"], " ", "made in a peanut-free facility, no milk, gluten free")
    assert not any(contains(a, text, terms) for a in ("peanut", "milk", "gluten"))
