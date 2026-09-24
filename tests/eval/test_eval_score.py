"""Scoring math on hand-built results: perfect, partial, empty, and edge cases."""

import json
from pathlib import Path

import pytest

from nanoif.eval.score import (
    claim_overlap,
    normalize_name,
    run_scoring,
    score_clean_paths,
    score_conflicts,
    score_defects,
    score_entities,
    score_facts,
    score_pronouns,
)

TRUTH_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "eval-story" / "truth.json"


@pytest.fixture(scope="module")
def truth():
    return json.loads(TRUTH_PATH.read_text(encoding="utf-8"))


def perfect_results(truth):
    """Everything the manifest asks for, phrased exactly as the manifest phrases it."""
    return {
        "entities": [
            {"name": e["name"], "type": e["type"], "aliases": e["aliases"]}
            for e in truth["entities"]
        ],
        "facts": [
            {
                "entity": f["entity"],
                "claim": f["claim"],
                "passage": f["passage"],
                "evidence_phrase": f["evidence_phrase"],
            }
            for f in truth["facts"]
        ],
        "conflicts": [
            {"passages": c["passages"], "intentional": c["intentional"]}
            for c in truth["contradictions"]
        ],
        "pronouns": [
            {"passage": p["passage"], "sentence": p["sentence"], "entity": p["expected"]}
            for p in truth["pronoun_cases"]
        ],
        "findings": [
            {"type": d["type"], "passages": d["passages"], "severity": d["expected_severity"]}
            for d in truth["defects"]
        ],
        "usage": {
            "calls": 20,
            "prompt_tokens": 100_000,
            "completion_tokens": 20_000,
            "reasoning_tokens": 5_000,
            "total_tokens": 120_000,
            "usd": 0.027,
            "usd_known": True,
            "profile": "exe",
            "model": "gpt-oss-120b",
        },
    }


def test_perfect_results_score_perfectly(truth):
    scores = run_scoring(truth, perfect_results(truth))
    m = scores["metrics"]
    assert m["entity_recall"] == 1.0 and m["entity_precision"] == 1.0
    assert m["distractor_hits"] == 0
    assert m["fact_recall"] == 1.0 and m["fact_precision"] == 1.0
    assert m["scene_state_leaks"] == 0
    assert m["conflict_recall"] == 1.0 and m["conflict_precision"] == 1.0
    assert m["intentional_flagged"] == 1
    assert m["defects_detected"] == 6 and m["defect_severity_matches"] == 6
    assert m["pronoun_accuracy"] == 1.0
    assert m["clean_path_false_positives"] == 0
    assert m["intentional_leaks"] == 0
    assert m["total_tokens"] == 120_000 and m["usd"] == 0.027
    assert scores["totals"]["model"] == "gpt-oss-120b"
    assert scores["entities"]["by_type"]["character"] == {"expected": 8, "found": 8, "recall": 1.0}


def test_empty_results_score_zero_without_crashing(truth):
    scores = run_scoring(truth, {})
    m = scores["metrics"]
    assert m["entity_recall"] == 0.0 and m["entity_precision"] == 0.0
    assert m["fact_recall"] == 0.0 and m["fact_precision"] == 0.0
    assert m["conflict_recall"] == 0.0 and m["conflict_precision"] == 0.0
    assert m["defects_detected"] == 0
    assert m["pronoun_accuracy"] == 0.0
    assert scores["pronouns"]["scored"] is False
    assert m["clean_path_false_positives"] == 0
    assert m["total_tokens"] == 0 and m["usd"] == 0.0
    assert scores["totals"]["usd_known"] is False
    assert len(scores["entities"]["missed"]) == 16
    assert len(scores["facts"]["missed"]) == 25


def test_partial_results_give_the_expected_fractions(truth):
    results = perfect_results(truth)
    results["entities"] = results["entities"][:8] + [{"name": "The Ghost of the Weir"}]
    results["facts"] = results["facts"][:10]
    results["conflicts"] = results["conflicts"][:1] + [{"passages": ["Day 4 EV", "The toll"]}]
    results["findings"] = results["findings"][:3]
    results["findings"][0]["severity"] = "critical"  # name_typo expected minor
    scores = run_scoring(truth, results)
    m = scores["metrics"]
    assert m["entity_recall"] == 0.5
    assert m["entity_precision"] == pytest.approx(8 / 9, abs=1e-4)
    assert scores["entities"]["spurious"] == ["The Ghost of the Weir"]
    assert m["fact_recall"] == 0.4 and m["fact_precision"] == 1.0
    assert m["conflict_recall"] == pytest.approx(1 / 3, abs=1e-4)
    assert m["conflict_precision"] == 0.5
    assert m["defects_detected"] == 3
    assert m["defect_severity_matches"] == 2
    assert scores["defects"]["per_defect"][0] == {
        "id": "d-typo",
        "type": "name_typo",
        "detected": True,
        "severity_ok": False,
        "expected_severity": "minor",
        "reported_severity": "critical",
    }


# -- entities ------------------------------------------------------------------


def test_entity_matching_is_alias_aware_and_case_insensitive(truth):
    reported = [
        {"name": "old tam"},
        {"name": "THE OLD MILL"},
        {"name": "Captain Marsh", "aliases": ["the captain"]},
        {"name": "Ferryman", "aliases": ["Wren"]},
        {"name": "The Wardens"},
    ]
    scores = score_entities(truth, reported)
    assert scores["matched"] == [
        "Oriel Marsh",
        "River Wardens",
        "Tamsin Reeve",
        "Weir House",
        "Wren Halloway",
    ]
    assert scores["precision"] == 1.0
    assert scores["recall"] == pytest.approx(5 / 16, abs=1e-4)


def test_distractor_entities_are_counted_and_hurt_precision(truth):
    scores = score_entities(
        truth, [{"name": "Wren Halloway"}, {"name": "No One"}, {"name": "Thirteen People"}]
    )
    assert scores["distractor_hits"] == ["No One", "Thirteen People"]
    assert scores["spurious"] == ["No One", "Thirteen People"]
    assert scores["precision"] == pytest.approx(1 / 3, abs=1e-4)


def test_normalize_name_strips_articles_and_possessives():
    assert normalize_name("The Old Mill's") == "old mill"
    assert normalize_name("  Maud Pellow’s stew ") == "maud pellow stew"
    assert normalize_name("Tam") == "tam"


# -- facts ---------------------------------------------------------------------


def test_claim_overlap_ignores_stopwords_and_plurals():
    assert claim_overlap("Pip is Wren's brother", "Wren's brother is Pip") == 1.0
    assert (
        claim_overlap("There are three keys to the Weir House", "the Weir House has three key")
        == 1.0
    )
    assert claim_overlap("Wren is seventeen", "Wren has a grey braid") == 0.5
    assert claim_overlap("", "anything") == 0.0


def test_fact_recall_accepts_reworded_claims_and_evidence_matches(truth):
    reported = [
        {"entity": "Wren", "claim": "Wren Halloway is seventeen years old"},
        {"entity": "Old Tam", "claim": "Her hair is in a grey braid."},
        {
            "entity": "the lantern",
            "claim": "Hung by the door",
            "evidence_phrase": "where it had hung for forty years",
        },
        {"entity": "Widow Kestle", "claim": "She keeps a knife for apples"},
        {"claim": "Pip is Wren's younger brother"},
    ]
    scores = score_facts(truth, reported)
    assert scores["recalled"] == ["f01", "f02", "f03", "f18"]
    assert scores["recall"] == 0.16
    assert scores["precision"] == 0.8


def test_fact_for_the_wrong_entity_does_not_count(truth):
    scores = score_facts(truth, [{"entity": "Pip Halloway", "claim": "Wren is seventeen"}])
    assert scores["recalled"] == []
    assert scores["precision"] == 0.0


def test_scene_state_facts_are_leaks(truth):
    reported = [
        {"entity": "Pip", "claim": "Pip was waiting on the jetty"},
        {"entity": "Maud Pellow", "claim": "The stew had gone cold and thick"},
        {
            "entity": "Weir House",
            "claim": "Smelled of a lamp lately blown out",
            "evidence_phrase": "the smell, which was of a lamp lately blown out",
        },
        {"entity": "Pip Halloway", "claim": "Pip is twelve"},
    ]
    scores = score_facts(truth, reported)
    assert scores["scene_state_leaks"] == 3
    assert scores["scene_state_precision"] == 0.25
    assert scores["recalled"] == ["f19"]


# -- conflicts -----------------------------------------------------------------


def test_conflict_recall_requires_every_planted_passage(truth):
    scores = score_conflicts(
        truth,
        [
            {"passages": ["Day 1 EV"]},
            {"passages": ["The widow's door", "Hollin Reach", "Day 2 EV"]},
        ],
    )
    # The second report spans c-pip-age and, as a superset, the one-passage c-widow-never-wife.
    assert scores["found"] == ["c-pip-age", "c-widow-never-wife"]
    assert scores["missed"] == ["c-tam-years"]
    assert scores["precision"] == 0.5


def test_conflict_precision_credits_conflict_like_defects_only(truth):
    reported = [
        {"passages": ["The weir", "The toll"]},
        {"passages": ["Day 1 EV", "The dark crossing"]},
        {"passages": ["Back at the ferry"]},
        {"passages": ["The last ferry"]},
    ]
    scores = score_conflicts(truth, reported)
    assert scores["recall"] == 0.0
    assert scores["precision"] == 0.5


def test_intentional_conflict_must_be_flagged_to_count_as_flagged(truth):
    unflagged = score_conflicts(truth, [{"passages": ["The widow's door"]}])
    assert unflagged["found"] == ["c-widow-never-wife"]
    assert unflagged["intentional_flagged"] == 0
    flagged = score_conflicts(truth, [{"passages": ["The widow's door"], "intentional": True}])
    assert flagged["intentional_flagged"] == 1


# -- defects and clean paths ---------------------------------------------------


def test_defect_detection_needs_matching_type_and_overlapping_passage(truth):
    findings = [
        {"type": "timeline", "passages": ["The toll"], "severity": "major"},
        {"type": "death_then_alive", "passages": ["Day 4 EV"], "severity": "critical"},
        {"type": "pov_slip", "passages": ["The last ferry"], "severity": "minor"},
    ]
    scores = score_defects(truth, findings)
    assert [r["id"] for r in scores["per_defect"] if r["detected"]] == ["d-timeline"]
    assert scores["detection_rate"] == pytest.approx(1 / 6, abs=1e-4)


def test_clean_path_false_positives_by_route_and_by_passages(truth):
    clean_route = truth["clean_paths"][0]["route"]
    findings = [
        {
            "type": "contradiction",
            "passages": ["The crossing", "Hollin Reach"],
            "severity": "major",
            "route": clean_route,
        },
        {"type": "contradiction", "passages": ["Day 2 EV"], "severity": "minor"},
        {
            "type": "contradiction",
            "passages": ["Hollin Reach", "The widow's door"],
            "severity": "major",
        },
        {"type": "world_rule", "passages": ["Day 1 EV", "The dark crossing"], "severity": "major"},
        {"type": "contradiction", "passages": ["The widow's door"], "severity": "minor"},
    ]
    scores = score_clean_paths(truth, findings)
    assert scores["paths"] == 2
    # Finding 1 is on the crossing route by declaration; finding 2 is on both routes by passages;
    # finding 3 lands on c-pip-age (planted); finding 4 is off every clean route;
    # finding 5 is the intentional mystery on the widow route.
    assert scores["false_positives"] == 3
    assert scores["intentional_leaks"] == 1
    kinds = {path: [row["kind"] for row in rows] for path, rows in scores["per_path"].items()}
    assert kinds["clean-crossing"] == ["false_positive", "false_positive"]
    assert kinds["clean-widow"] == ["false_positive", "intentional_leak"]


def test_declared_route_that_is_not_clean_is_ignored(truth):
    finding = {
        "type": "x",
        "passages": ["Day 1 EV"],
        "severity": "minor",
        "route": ["Start", "Day 1 EV", "The chapel path"],
    }
    assert score_clean_paths(truth, [finding])["false_positives"] == 0


# -- pronouns ------------------------------------------------------------------


def test_pronoun_scoring_uses_aliases_and_null_for_ambiguous(truth):
    reported = [
        {"passage": "Day 1 EV", "sentence": "as she had every morning", "entity": "Wren"},
        {
            "passage": "Day 1 EV",
            "sentence": "her grey braid tucked into the collar",
            "entity": "Old Tam",
        },
        {"passage": "The crossing", "sentence": "the way he always stood", "entity": "Pip"},
        {
            "passage": "The warden's ledger",
            "sentence": "Marsh looked at Pip, and he said nothing for a long moment.",
            "entity": None,
        },
        {
            "passage": "The widow's door",
            "sentence": "The widow looked at Wren for a long moment, and she did not look away.",
            "entity": "Widow Kestle",
        },
    ]
    scores = score_pronouns(truth, reported)
    assert scores["scored"] is True
    assert scores["resolvable_correct"] == 2
    assert scores["ambiguous_correct"] == 1
    assert scores["accuracy"] == 0.375
