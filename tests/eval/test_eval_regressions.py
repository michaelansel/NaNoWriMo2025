"""The eval replays 2025's known false positives through the Continuity Editor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nanoif.eval.regressions import review_regressions
from nanoif.llm.fake import FakeLLM
from nanoif.review.units import ReviewStory

REGRESSIONS = Path(__file__).resolve().parents[1] / "fixtures" / "regressions"
NO_FINDINGS = {"findings": [], "notes": "Checked the sizes and the sword."}


def replay_2025(call):
    """Answer each regression unit with its original 2025 false positive, quoted verbatim."""
    name = call.tag.split(":", 1)[1]
    for root in REGRESSIONS.iterdir():
        expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
        if expected["passage_under_review"] != name:
            continue
        story = ReviewStory.from_source(root / "src")
        other = expected["other_passage"]
        return {"findings": [{
            "type": expected["type"], "source": "path",
            "other": {"passage_id": story.ids[other], "fact_id": None},
            "description": expected["original_finding"], "severity": "major", "confidence": "high",
            "quotes": [{"passage_id": story.ids[p], "text": q} for p, q in expected["quotes"].items()],
        }], "notes": ""}
    return NO_FINDINGS


@pytest.mark.intent("AC-continuity-review-27")
def test_no_finding_on_either_regression_scores_zero():
    result = review_regressions(REGRESSIONS, FakeLLM(lambda call: NO_FINDINGS))
    assert result["false_positives"] == 0 and result["ok"]
    assert [(f["name"], f["status"], f["findings"]) for f in result["fixtures"]] == [
        ("height-sitting-vs-standing", "ok", 0),
        ("sword-hand-after-fall", "ok", 0),
    ]


@pytest.mark.intent("AC-continuity-review-27")
def test_repeating_the_2025_findings_counts_each_as_a_false_positive():
    result = review_regressions(REGRESSIONS, FakeLLM(replay_2025))
    assert result["false_positives"] == 2 and result["ok"]
    assert all(f["descriptions"] for f in result["fixtures"])


def test_a_failed_call_is_an_error_never_zero_findings():
    def flaky(call):
        if call.tag == "continuity:The fall":
            return FakeLLM.transport_error()
        return NO_FINDINGS

    result = review_regressions(REGRESSIONS, FakeLLM(flaky))
    assert not result["ok"]
    sword = next(f for f in result["fixtures"] if f["name"] == "sword-hand-after-fall")
    assert sword["status"] == "error" and sword["findings"] is None and "LLMTransportError" in sword["reason"]


def test_review_story_from_source_matches_the_test_helper():
    story = ReviewStory.from_source(REGRESSIONS / "sword-hand-after-fall" / "src")
    assert {"The fall", "Day 6 EV"} <= set(story.content)
