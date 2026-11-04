"""Kaggle downloads and the Spark reader options that parse them exactly."""

from __future__ import annotations

import os
import re

from .config import OFF_DATASET, OFF_FILE, RANKING_DATASET, RANKING_FILE

# The Open Food Facts TSV has no quoting, a few stray "\r" inside fields and some fields over 131k chars.
OFF_READ_OPTIONS = {"header": "true", "sep": "\t", "quote": "", "lineSep": "\n", "multiLine": "false",
                    "inferSchema": "false", "encoding": "UTF-8"}
RANKING_READ_OPTIONS = {"header": "true", "inferSchema": "false", "encoding": "UTF-8"}


def download(cache_dir: str | None = None) -> tuple[str, str]:
    """Download (or reuse) both pinned datasets and return (open_food_facts_tsv, candy_ranking_csv)."""
    if cache_dir:
        os.environ["KAGGLEHUB_CACHE"] = cache_dir  # read by kagglehub at import time
    import kagglehub

    off = os.path.join(kagglehub.dataset_download(OFF_DATASET), OFF_FILE)
    ranking = os.path.join(kagglehub.dataset_download(RANKING_DATASET), RANKING_FILE)
    return off, ranking


_FEED_FILE = re.compile(r"^openfoodfacts_products_(\d+)_(\d+)\.json\.gz$")


def feed_files(names: list[str]) -> list[dict]:
    """Parse change-feed file names into {file_name, from_ts, to_ts}, oldest first; other names are ignored."""
    out = []
    for name in names:
        m = _FEED_FILE.match(name.strip())
        if m:
            out.append({"file_name": name.strip(), "from_ts": int(m[1]), "to_ts": int(m[2])})
    return sorted(out, key=lambda f: f["from_ts"])


def feed_gaps(files: list[dict]) -> list[dict]:
    """Windows the archive is missing: each file should start where the previous one ended."""
    return [{"after_file": a["file_name"], "missing_from_ts": a["to_ts"], "missing_to_ts": b["from_ts"]}
            for a, b in zip(files, files[1:], strict=False) if b["from_ts"] != a["to_ts"]]
