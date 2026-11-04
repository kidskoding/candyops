import csv
from pathlib import Path

import pytest

SEEDS = Path(__file__).resolve().parents[1] / "dbt" / "seeds"


def read_seed(name: str) -> list[dict]:
    with open(SEEDS / f"{name}.csv", newline="", encoding="utf-8") as fh:
        return [{k: (v or None) for k, v in row.items()} for row in csv.DictReader(fh)]


@pytest.fixture(scope="session")
def aliases():
    return read_seed("candy_aliases")


@pytest.fixture(scope="session")
def terms():
    return {r["allergen"]: r for r in read_seed("allergen_terms")}


@pytest.fixture(scope="session")
def rules():
    return {r["rule"]: r["pattern"] for r in read_seed("text_rules")}
