"""Kaggle downloads and the Spark reader options that parse them exactly."""

from __future__ import annotations

import os

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
