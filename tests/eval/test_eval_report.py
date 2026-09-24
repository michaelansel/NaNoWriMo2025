"""Markdown/JSON rendering and baseline diffing."""

import json
from pathlib import Path

import pytest

from nanoif.eval.report import baseline_metrics, diff_against_baseline, render_markdown, to_json
from nanoif.eval.score import run_scoring

TRUTH_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "eval-story" / "truth.json"


@pytest.fixture(scope="module")
def truth():
    return json.loads(TRUTH_PATH.read_text(encoding="utf-8"))


def base(**overrides):
    metrics = {
        "entity_recall": 0.75,
        "fact_recall": 0.8,
        "conflict_recall": 0.6667,
        "defects_detected": 4,
        "clean_path_false_positives": 1,
        "total_tokens": 100_000,
        "usd": 0.02,
    }
    metrics.update(overrides)
    return {"profile": "exe", "metrics": metrics}


def test_baseline_metrics_accepts_both_shapes():
    assert baseline_metrics({"metrics": {"a": 1, "b": "x"}}) == {"a": 1}
    assert baseline_metrics({"a": 0.5, "profile": "exe", "flag": True}) == {"a": 0.5}


def test_diff_flags_quality_drops_and_false_positive_rises():
    current = {
        "entity_recall": 0.7,
        "fact_recall": 0.9,
        "conflict_recall": 0.6667,
        "defects_detected": 4,
        "clean_path_false_positives": 2,
        "total_tokens": 100_000,
        "usd": 0.02,
    }
    diff = diff_against_baseline({"metrics": current}, base())
    assert diff["ok"] is False
    assert sorted(r["metric"] for r in diff["regressions"]) == [
        "clean_path_false_positives",
        "entity_recall",
    ]
    assert [r["metric"] for r in diff["improvements"]] == ["fact_recall"]
    assert {r["metric"] for r in diff["unchanged"]} == {
        "conflict_recall",
        "defects_detected",
        "total_tokens",
        "usd",
    }


def test_cost_metrics_have_a_tolerance():
    within = {**base()["metrics"], "total_tokens": 124_000, "usd": 0.0249}
    assert diff_against_baseline({"metrics": within}, base())["ok"] is True
    beyond = {**base()["metrics"], "total_tokens": 126_000}
    diff = diff_against_baseline({"metrics": beyond}, base())
    assert [r["metric"] for r in diff["regressions"]] == ["total_tokens"]
    cheaper = {**base()["metrics"], "usd": 0.01}
    assert [r["metric"] for r in diff_against_baseline(cheaper, base())["improvements"]] == ["usd"]


def test_metric_missing_from_scores_is_not_ok():
    current = {k: v for k, v in base()["metrics"].items() if k != "fact_recall"}
    diff = diff_against_baseline({"metrics": current}, base())
    assert diff["missing"] == ["fact_recall"]
    assert diff["ok"] is False


def test_markdown_without_baseline_lists_metrics_and_detail(truth):
    scores = run_scoring(truth, {"entities": [{"name": "Wren"}]})
    text = render_markdown(scores)
    assert text.startswith("| Metric | Value |\n|---|---|\n")
    assert "| Entity recall | 0.0625 |" in text
    assert "| Clean-path false positives | 0 |" in text
    assert "Pronouns: not scored" in text
    assert "(rate unknown)" in text
    assert "Baseline" not in text


def test_markdown_with_baseline_marks_regressions(truth):
    scores = run_scoring(truth, {"entities": [{"name": "Wren"}]})
    text = render_markdown(scores, base())
    assert "| Metric | Value | Baseline | Change |" in text
    assert "| Entity recall | 0.0625 | 0.75 | regression |" in text
    assert "| Clean-path false positives | 0 | 1 | improved |" in text
    assert (
        "Baseline: regressions in entity_recall, fact_recall, conflict_recall, defects_detected."
        in text
    )


def test_markdown_reports_clean_baseline(truth):
    scores = run_scoring(truth, {})
    zero = {k: 0 for k in scores["metrics"]}
    assert "Baseline: no metric below baseline." in render_markdown(scores, {"metrics": zero})


def test_json_is_deterministic_and_round_trips(truth):
    scores = run_scoring(truth, {"facts": [{"claim": "Wren is seventeen"}]})
    text = to_json(scores)
    assert text.endswith("}\n")
    assert json.loads(text) == json.loads(to_json(json.loads(text)))
    assert json.loads(text)["metrics"]["fact_recall"] == 0.04
