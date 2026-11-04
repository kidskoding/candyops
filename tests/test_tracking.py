from contextlib import contextmanager
from types import SimpleNamespace

from candyops.tracking import log_runs, run_records

BOWLS = [
    {"restriction": "no_restriction", "candies_allowed": 83, "avg_win_percent": 70.0,
     "popularity_kept_pct": 100.0, "median_sugars_100g": 50.0, "bowl": "Reese's Peanut Butter cup, Twix"},
    {"restriction": "peanut_free", "candies_allowed": 20, "avg_win_percent": 56.0,
     "popularity_kept_pct": 80.0, "median_sugars_100g": None, "bowl": "Twix"},
]
METHODS = [{"method": "naive", "candies_matched": 60, "products_matched": 900, "us_products_matched": 700,
            "non_candy_products": 40}]


class FakeMlflow:
    def __init__(self):
        self.runs, self.stack = [], []

    def set_experiment(self, path):
        self.experiment = path

    @contextmanager
    def start_run(self, run_name, nested=False):
        run = {"name": run_name, "nested": nested, "params": {}, "metrics": {}, "tags": {}}
        self.runs.append(run)
        self.stack.append(run)
        yield SimpleNamespace(info=SimpleNamespace(run_id=f"id-{len(self.runs)}"))
        self.stack.pop()

    def log_params(self, p):
        self.stack[-1]["params"].update(p)

    def log_metrics(self, m):
        self.stack[-1]["metrics"].update(m)

    def set_tags(self, t):
        self.stack[-1]["tags"].update(t)


def test_one_record_per_bowl_and_method_with_float_metrics_and_no_nulls():
    recs = run_records(BOWLS, METHODS)
    assert [r["run_name"] for r in recs] == ["bowl:no_restriction", "bowl:peanut_free", "match:naive"]
    assert "median_sugars_100g" not in recs[1]["metrics"]
    assert all(isinstance(v, float) for r in recs for v in r["metrics"].values())


def test_log_runs_nests_every_record_under_one_parent():
    fake = FakeMlflow()
    run_id = log_runs(fake, run_records(BOWLS, METHODS), "/Users/me/exp", "pipeline", {"schema": "candyops"})
    assert run_id == "id-1" and fake.experiment == "/Users/me/exp"
    assert [r["nested"] for r in fake.runs] == [False, True, True, True]
    assert fake.runs[0]["tags"]["data_source"] == "kaggle" and fake.runs[0]["params"] == {"schema": "candyops"}
