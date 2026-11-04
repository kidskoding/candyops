"""Kaggle downloads and the Spark reader options that parse them exactly."""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys

from .config import OFF_DATASET, OFF_FILE, RANKING_DATASET, RANKING_FILE

# The Open Food Facts TSV has no quoting, a few stray "\r" inside fields and some fields over 131k chars.
OFF_READ_OPTIONS = {"header": "true", "sep": "\t", "quote": "", "lineSep": "\n", "multiLine": "false",
                    "inferSchema": "false", "encoding": "UTF-8"}
RANKING_READ_OPTIONS = {"header": "true", "inferSchema": "false", "encoding": "UTF-8"}


KAGGLEHUB_REQUIREMENT = "kagglehub==1.0.3"


def cached_file(cache_dir: str, dataset: str, file: str) -> str:
    """Where kagglehub keeps a pinned dataset file: <cache>/datasets/<owner>/<name>/versions/<n>/<file>."""
    return os.path.join(cache_dir, "datasets", dataset, file)


def download(cache_dir: str | None = None) -> tuple[str, str]:
    """Download (or reuse) both pinned datasets and return (open_food_facts_tsv, candy_ranking_csv).

    When both files are already in cache_dir, kagglehub is not imported or installed, so reruns do not depend on PyPI.
    """
    if cache_dir:
        cached = (cached_file(cache_dir, OFF_DATASET, OFF_FILE), cached_file(cache_dir, RANKING_DATASET, RANKING_FILE))
        if all(os.path.isfile(path) for path in cached):
            return cached
        os.environ["KAGGLEHUB_CACHE"] = cache_dir  # read by kagglehub at import time
    try:
        import kagglehub
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", KAGGLEHUB_REQUIREMENT], check=True)
        importlib.invalidate_caches()  # let this process see the package pip just installed
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
