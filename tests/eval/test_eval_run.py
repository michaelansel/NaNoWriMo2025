"""``nanoif ai eval`` runs a full extraction, reviews with its canon, and scores both."""

from __future__ import annotations

from pathlib import Path

import pytest

from nanoif.eval import run as eval_run
from nanoif.eval.run import run_eval
from nanoif.llm.errors import LLMSpendCapReached
from nanoif.llm.fake import FakeLLM

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eval-story"
EMPTY = {"summary": "", "entities": [], "references": []}
NO_FINDINGS = {"findings": [], "notes": "Checked names and numbers."}


def tam(facts, references=()):
    return {
        "summary": "Tam at the ferry.",
        "entities": [
            {
                "name": "Tamsin Reeve",
                "type": "character",
                "aliases": ["Old Tam", "Tam"],
                "role": "ferry keeper",
                "facts": [{"claim": c, "quote": q, "kind": "event"} for c, q in facts],
            }
        ],
        "references": list(references),
    }


EXTRACTIONS = {
    "Day 1 EV": tam(
        [("Tamsin Reeve has carried the lantern for forty years", "every working day of those forty years")],
        [{"quote": "her grey braid tucked into the collar", "pronoun": "her", "entity": "Tamsin Reeve"}],
    ),
    "Back at the ferry": tam([("Tam has poled the river for thirty years", "Thirty years I've poled this river")]),
}


def respond(call):
    tag = call.tag
    if tag.startswith("bible-extract:"):
        return EXTRACTIONS.get(tag.split(":", 1)[1], EMPTY)
    if tag == "bible-resolve":
        return {"merges": [], "drop": []}
    if tag.startswith("bible-reconcile"):
        return {"entities": [{"slug": "tamsin-reeve", "duplicates": [], "conflicts": [
            {"a": "tamsin-reeve#1", "b": "tamsin-reeve#2", "note": "forty or thirty years"}]}]}
    return NO_FINDINGS


@pytest.mark.intent("ADR-020")
def test_eval_scores_the_extracted_bible(tmp_path):
    client = FakeLLM(respond)
    outcome = run_eval(FIXTURE, client, tmp_path / "story", env={"NANOIF_RUNNER": "local"})
    scores = outcome.scores
    assert outcome.extraction["status"] == "ok" and outcome.ok
    assert "Tamsin Reeve" in scores["entities"]["matched"]
    assert scores["entities"]["distractor_hits"] == []
    assert "f04" in scores["facts"]["recalled"]
    assert scores["conflicts"]["found"] == ["c-tam-years"]
    assert scores["pronouns"]["scored"] and scores["pronouns"]["resolvable_correct"] == 1
    assert scores["review_conflicts"]["reported"] == 0
    assert "review_conflict_recall" in scores["metrics"] and "entity_recall" in scores["metrics"]
    assert "skipped_metrics" not in scores
    assert not hasattr(eval_run, "EXTRACTION_SKIPPED")
    extract_calls = [c for c in client.calls if c.tag.startswith("bible-extract:")]
    assert len(extract_calls) == 16
    continuity = [c for c in client.calls if c.tag.startswith("continuity:")]
    unit = next(c for c in continuity if c.tag == "continuity:Back at the ferry")
    assert "<<<BEGIN CANON [B]>>>" in unit.user and "tamsin-reeve#2" in unit.user
    assert "Extraction: ok" in outcome.markdown


@pytest.mark.intent("AC-continuity-review-27")
def test_eval_replays_the_2025_false_positives(tmp_path):
    outcome = run_eval(FIXTURE, FakeLLM(respond), tmp_path / "story", env={"NANOIF_RUNNER": "local"})
    assert outcome.scores["metrics"]["regression_false_positives"] == 0
    assert [f["name"] for f in outcome.scores["regressions"]["fixtures"]] == [
        "height-sitting-vs-standing", "sword-hand-after-fall"]
    assert "Regressions: height-sitting-vs-standing 0 findings, sword-hand-after-fall 0 findings." in outcome.markdown


def test_a_regression_that_could_not_run_fails_the_eval(tmp_path):
    def flaky(call):
        if call.tag == "continuity:The fall":
            return FakeLLM.transport_error()
        return respond(call)

    outcome = run_eval(FIXTURE, FakeLLM(flaky), tmp_path / "story", env={"NANOIF_RUNNER": "local"})
    assert not outcome.ok and outcome.review_ok
    assert "sword-hand-after-fall could not run" in outcome.markdown


class CappedLLM(FakeLLM):
    def check_spend(self, estimate_usd: float = 0.0) -> None:
        raise LLMSpendCapReached(
            "cap", reason="monthly AI spend cap reached", month_usd=10.0, cap_usd=10.0
        )


@pytest.mark.intent("ADR-020")
def test_an_extraction_halt_marks_the_bible_sections_skipped_and_fails_the_eval(tmp_path):
    outcome = run_eval(FIXTURE, CappedLLM(respond), tmp_path / "story", env={"NANOIF_RUNNER": "local"})
    scores = outcome.scores
    reason = "extraction halted: monthly AI spend cap reached"
    for section in ("entities", "facts", "pronouns", "conflicts"):
        assert scores[section] == {"skipped": reason}
    assert scores["skipped_metrics"]["conflict_recall"] == reason
    assert "entity_recall" not in scores["metrics"]
    assert not outcome.ok and outcome.extraction["status"] == "halted"
    assert f"Entities: skipped ({reason})." in outcome.markdown


def test_a_partial_extraction_is_scored_but_fails_the_eval(tmp_path):
    def flaky(call):
        if call.tag == "bible-extract:Day 1 EV":
            return FakeLLM.transport_error()
        return respond(call)

    outcome = run_eval(FIXTURE, FakeLLM(flaky), tmp_path / "story", env={"NANOIF_RUNNER": "local"})
    assert outcome.extraction["status"] == "partial" and not outcome.ok
    assert "entity_recall" in outcome.scores["metrics"]


def test_review_conflicts_carry_the_finding_quotes():
    artifact = {
        "llm": {},
        "editors": [
            {
                "name": "continuity",
                "findings": [
                    {
                        "type": "number",
                        "severity": "major",
                        "key": "f-00000001",
                        "description": "Pip's age differs.",
                        "passages": [{"name": "Hollin Reach"}, {"name": "The widow's door"}],
                        "quotes": [
                            {"passage": "Hollin Reach", "text": "Wren's brother was twelve"},
                            {"passage": "The widow's door", "text": "Eleven years old"},
                        ],
                    }
                ],
            }
        ],
    }
    (conflict,) = eval_run.results_from_review(artifact)["review_conflicts"]
    assert conflict["quotes"] == ["Wren's brother was twelve", "Eleven years old"]


@pytest.mark.intent("ADR-024")
def test_a_mysterys_facts_are_scored_as_declared_entries():
    from nanoif.bible.assemble import Bible, BibleFact, Freshness, Mystery

    fact = BibleFact("widow-kestle#4", "The Widow Kestle was never anyone's wife",
                     "I was never anyone's wife", "The widow's door", "trait")
    bible = Bible(
        cache_present=True, passage_count=1, entities=(), conflicts=(),
        mysteries=(Mystery("c-widow-never-wife", 14, (), (fact,)),), unmatched=(),
        freshness=Freshness(None, None, None, "success", (), (), (), ()),
    )
    (entry,) = eval_run.results_from_bible(bible, None)["conflicts"]
    assert entry == {"id": "c-widow-never-wife", "passages": ["The widow's door"],
                     "quotes": ["I was never anyone's wife"], "intentional": True,
                     "declared": True}
