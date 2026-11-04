import sys

from candyops.config import OFF_DATASET, OFF_FILE, RANKING_DATASET, RANKING_FILE
from candyops.sources import cached_file, download, feed_files, feed_gaps

INDEX = """openfoodfacts_products_1793687333_1793773764.json.gz
openfoodfacts_products_1793601055_1793687333.json.gz
openfoodfacts_products_1793428456_1793514332.json.gz
index.txt
"""


def test_feed_files_are_parsed_and_sorted_oldest_first():
    files = feed_files(INDEX.splitlines())
    assert [f["from_ts"] for f in files] == [1793428456, 1793601055, 1793687333]
    assert files[-1] == {"file_name": "openfoodfacts_products_1793687333_1793773764.json.gz",
                         "from_ts": 1793687333, "to_ts": 1793773764}


def test_a_missing_day_is_reported_as_a_gap():
    gaps = feed_gaps(feed_files(INDEX.splitlines()))
    assert gaps == [{"after_file": "openfoodfacts_products_1793428456_1793514332.json.gz",
                     "missing_from_ts": 1793514332, "missing_to_ts": 1793601055}]


def test_contiguous_files_have_no_gaps():
    assert feed_gaps(feed_files(INDEX.splitlines()[:2])) == []


def test_download_reuses_cached_files_without_kagglehub(tmp_path, monkeypatch):
    for dataset, name in [(OFF_DATASET, OFF_FILE), (RANKING_DATASET, RANKING_FILE)]:
        path = tmp_path / "datasets" / dataset / name
        path.parent.mkdir(parents=True)
        path.write_text("x")
    monkeypatch.setitem(sys.modules, "kagglehub", None)  # any import of kagglehub would now raise ImportError
    off, ranking = download(str(tmp_path))
    assert off == cached_file(str(tmp_path), OFF_DATASET, OFF_FILE)
    assert ranking.endswith("versions/1/candy-data.csv")
