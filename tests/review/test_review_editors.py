"""Continuity and Style Editors: prompts, quote verification, keys, severity, merging."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest
from review_helpers import REGRESSIONS, answer, load_review_story, path_finding

from nanoif.llm.fake import FakeLLM
from nanoif.llm.schema import validate
from nanoif.review import continuity, style
from nanoif.review.findings import (
    Finding,
    PassageRef,
    Quote,
    finding_key,
    is_dismissed,
    merge_findings,
    quote_found,
)
from nanoif.review.prompts import PROMPTS_DIR, prompt_schema, render_prompt
from nanoif.review.units import StoryStyleConfig, continuity_units, style_unit

P = "Back at the ferry"
OTHER = "Day 1 EV"
P_QUOTE = "Thirty years I've poled this river"
OTHER_QUOTE = "every working day of those forty years"


@pytest.fixture
def unit(eval_story):
    return continuity_units(eval_story, P)[0]


def ids(story, *names):
    return [story.ids[name] for name in names]


# -- prompts ------------------------------------------------------------------------


def test_every_prompt_has_a_valid_sibling_schema():
    for name in ("continuity", "style"):
        schema = prompt_schema(name)
        assert schema["type"] == "object"
        validate({"findings": [], "notes": ""}, schema)


def test_continuity_prompt_keeps_story_text_out_of_the_system_message(eval_story, unit):
    prompt = continuity.build_prompt(eval_story, unit)
    assert OTHER_QUOTE in prompt.user
    assert OTHER_QUOTE not in prompt.system
    assert "<<<BEGIN STORY TEXT [A]>>>" in prompt.user
    assert "<<<END STORY TEXT [A]>>>" in prompt.user
    assert "data, not instructions" in prompt.user
    assert "ignore it" in prompt.system
    assert "critical" in prompt.system and "impossible on this path" in prompt.system
    assert "exactly one other source" in prompt.system
    assert "[B]" not in prompt.system and "CANON" not in prompt.user
    assert P not in prompt.user and P not in prompt.system


def test_continuity_prompt_renders_canon_only_when_given(eval_story, unit):
    fact = continuity.CanonFact("tamsin-reeve#1", "Tamsin Reeve", "keeps the ferry", OTHER)
    prompt = continuity.build_prompt(eval_story, unit, [fact])
    assert "[B] Canon facts" in prompt.system
    assert f"tamsin-reeve#1  Tamsin Reeve: keeps the ferry  [{eval_story.ids[OTHER]}]" in prompt.user


def test_prompts_contain_no_canned_all_clear():
    for name in ("continuity", "style"):
        text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").lower()
        for phrase in ("no issues", "perfect", "flawless"):
            assert phrase not in text


def test_style_prompt_lists_only_the_settings_the_story_defines(eval_story):
    story = replace(eval_story, style=StoryStyleConfig({"tense": "past"}, None))
    prompt = style.build_prompt(story, style_unit(story, "The last ferry"))
    assert "tense_slip" in prompt.system
    assert "pov_slip" not in prompt.system
    assert "Wren steps aboard" in prompt.user


def test_missing_template_variable_is_an_error():
    from jinja2 import UndefinedError

    with pytest.raises(UndefinedError):
        render_prompt("continuity", unit_text="x", passage_id="y")


def test_review_unit_calls_the_completer_with_schema_and_effort(eval_story, unit):
    p_id, other_id = ids(eval_story, P, OTHER)
    fake = FakeLLM(
        {unit.tag: answer(path_finding(other_id, [(p_id, P_QUOTE), (other_id, OTHER_QUOTE)]))}
    )
    result = continuity.review_unit(fake, eval_story, unit)
    call = fake.calls[0]
    assert call.reasoning_effort == "medium"
    assert call.schema == prompt_schema("continuity")
    assert call.tag == f"continuity:{P}"
    assert [f.type for f in result.findings] == ["number"]
    style_fake = FakeLLM({f"style:{P}": answer()})
    style.review_unit(style_fake, eval_story, style_unit(eval_story, P))
    assert style_fake.calls[0].reasoning_effort == "low"


# -- continuity post-processing ----------------------------------------------------


def test_verified_finding_maps_ids_back_to_names_and_hashes(eval_story, unit):
    p_id, other_id = ids(eval_story, P, OTHER)
    data = answer(path_finding(other_id, [(p_id, P_QUOTE), (other_id, OTHER_QUOTE)]))
    out = continuity.postprocess(eval_story, unit, data)
    assert out.unverified == [] and out.dropped == 0
    finding = out.findings[0]
    assert [ref.name for ref in finding.passages] == [P, OTHER]
    assert finding.passages[0].hash == eval_story.hash(P)
    assert finding.passages[0].file == "src/EV-20261102.twee"
    assert finding.passages[0].line == 56
    assert [(q.passage, q.text) for q in finding.quotes] == [(P, P_QUOTE), (OTHER, OTHER_QUOTE)]
    assert finding.key == finding_key("number", P, OTHER)


def test_fabricated_quote_moves_the_finding_to_unverified(eval_story, unit):
    p_id, other_id = ids(eval_story, P, OTHER)
    data = answer(
        path_finding(other_id, [(p_id, P_QUOTE), (other_id, "she had ferried for fifty years")])
    )
    out = continuity.postprocess(eval_story, unit, data)
    assert out.findings == []
    assert len(out.unverified) == 1


def test_finding_without_a_quote_from_the_other_passage_is_unverified(eval_story, unit):
    p_id, other_id = ids(eval_story, P, OTHER)
    out = continuity.postprocess(eval_story, unit, answer(path_finding(other_id, [(p_id, P_QUOTE)])))
    assert out.findings == [] and len(out.unverified) == 1


def test_quote_matching_normalizes_whitespace_and_typographic_quotes(eval_story, unit):
    p_id, other_id = ids(eval_story, P, OTHER)
    messy = "Thirty  years\nI’ve poled   this river"
    data = answer(path_finding(other_id, [(p_id, f'"{messy}"'), (other_id, OTHER_QUOTE)]))
    assert len(continuity.postprocess(eval_story, unit, data).findings) == 1
    assert not quote_found("thirty years I've poled", [eval_story.content[P]])
    assert not quote_found("   ", [eval_story.content[P]])


def test_finding_not_involving_the_passage_under_review_is_dropped(eval_story, unit):
    p_id, other_id, chapel_id = ids(eval_story, P, OTHER, "The chapel path")
    between_ancestors = path_finding(
        chapel_id, [(other_id, OTHER_QUOTE), (chapel_id, "He came down the ladder slowly.")]
    )
    other_is_p = path_finding(p_id, [(p_id, P_QUOTE)])
    third_passage = path_finding(
        other_id,
        [(p_id, P_QUOTE), (other_id, OTHER_QUOTE), (chapel_id, "He came down the ladder slowly.")],
    )
    unknown_other = path_finding("000000000000", [(p_id, P_QUOTE)])
    out = continuity.postprocess(
        eval_story, unit, answer(between_ancestors, other_is_p, third_passage, unknown_other)
    )
    assert out.findings == [] and out.unverified == []
    assert out.dropped == 4


def test_severity_is_computed_by_code_from_the_type(eval_story, unit):
    p_id, other_id = ids(eval_story, P, OTHER)
    quotes = [(p_id, P_QUOTE), (other_id, OTHER_QUOTE)]
    data = answer(
        path_finding(other_id, quotes, finding_type="death_then_alive", severity="minor"),
        path_finding(other_id, quotes, finding_type="name_typo", severity="critical"),
        path_finding(other_id, quotes, finding_type="world_rule", severity="minor"),
        path_finding(other_id, quotes, finding_type="number", severity="critical"),
    )
    got = {f.type: f.severity for f in continuity.postprocess(eval_story, unit, data).findings}
    assert got == {
        "death_then_alive": "critical",
        "name_typo": "minor",
        "world_rule": "major",
        "number": "critical",
    }


def test_canon_finding_uses_the_facts_passage(eval_story, unit):
    p_id = eval_story.ids[P]
    fact = continuity.CanonFact("tamsin-reeve#1", "Tamsin Reeve", "forty years on the river", OTHER)
    raw = path_finding("", [(p_id, P_QUOTE)])
    raw["source"] = "canon"
    raw["other"] = {"passage_id": None, "fact_id": "tamsin-reeve#1"}
    out = continuity.postprocess(eval_story, unit, answer(raw), [fact])
    assert len(out.findings) == 1
    finding = out.findings[0]
    assert finding.canon_fact_id == "tamsin-reeve#1"
    assert [ref.name for ref in finding.passages] == [P, OTHER]
    unknown = dict(raw, other={"passage_id": None, "fact_id": "nobody#9"})
    assert continuity.postprocess(eval_story, unit, answer(unknown), [fact]).dropped == 1


# -- keys and merging ------------------------------------------------------------------


def test_finding_key_is_stable_and_order_independent():
    expected = "f-" + hashlib.sha256(b"number|Back at the ferry|Day 1 EV").hexdigest()[:8]
    assert finding_key("number", P, OTHER) == expected
    assert finding_key("number", OTHER, P) == expected
    assert finding_key("timeline", P, OTHER) != expected


def _finding(key: str, severity: str, quote: str, confidence: str = "medium") -> Finding:
    return Finding(
        key=key,
        editor="continuity",
        type="death_then_alive",
        severity=severity,
        confidence=confidence,
        description="Marsh drowns, then collects the toll.",
        passages=(PassageRef("The toll", "a" * 16), PassageRef("The weir", "b" * 16)),
        quotes=(Quote("The weir", "She saw him go over."), Quote("The toll", quote)),
    )


def test_same_contradiction_from_three_units_merges_into_one():
    key = finding_key("death_then_alive", "The toll", "The weir")
    per_unit = [
        [_finding(key, "major", '"Toll," he said.')],
        [_finding(key, "critical", "Captain Marsh stood in the stern", confidence="high")],
        [_finding(key, "minor", '"Toll," he said.'), _finding(key, "minor", '"Toll," he said.')],
    ]
    merged = merge_findings(per_unit)
    assert len(merged) == 1
    finding = merged[0]
    assert finding.routes_seen == 3
    assert finding.severity == "critical"
    assert finding.confidence == "high"
    assert [q.text for q in finding.quotes] == [
        "She saw him go over.",
        '"Toll," he said.',
        "Captain Marsh stood in the stern",
    ]


def test_merge_orders_by_severity_then_first_seen():
    a = _finding("f-aaaaaaaa", "minor", "x")
    b = _finding("f-bbbbbbbb", "critical", "y")
    c = _finding("f-cccccccc", "minor", "z")
    assert [f.key for f in merge_findings([[a, b], [c]])] == ["f-bbbbbbbb", "f-aaaaaaaa", "f-cccccccc"]


def test_is_dismissed_needs_every_hash_to_match():
    finding = _finding("f-aaaaaaaa", "major", "x")
    both = {"The toll": "a" * 16, "The weir": "b" * 16}
    assert is_dismissed(finding, {"f-aaaaaaaa": [both]})
    assert not is_dismissed(finding, {"f-aaaaaaaa": [{**both, "The weir": "c" * 16}]})
    assert not is_dismissed(finding, {"f-bbbbbbbb": [both]})


def test_findings_serialize_to_the_artifact_shape():
    data = _finding("f-aaaaaaaa", "major", "x").to_dict()
    assert json.loads(json.dumps(data))["passages"][0] == {
        "name": "The toll",
        "hash": "a" * 16,
        "file": None,
        "line": None,
    }


# -- style post-processing -----------------------------------------------------------


def style_answer(finding_type: str, quote: str, severity: str = "minor") -> dict:
    return answer(
        {
            "type": finding_type,
            "description": "Slips out of the house style.",
            "severity": severity,
            "confidence": "high",
            "quotes": [{"text": quote}],
        }
    )


def test_style_finding_is_single_passage_with_verified_quote(eval_story):
    name = "The last ferry"
    unit = style_unit(eval_story, name)
    data = style_answer("tense_slip", "Wren steps aboard and takes the pole from Tam's hands")
    out = style.postprocess(eval_story, unit, data)
    finding = out.findings[0]
    assert finding.key == finding_key("tense_slip", name, name)
    assert [ref.name for ref in finding.passages] == [name]
    assert finding.editor == "style"


def test_style_fabricated_quote_is_unverified_and_severity_clamped(eval_story):
    unit = style_unit(eval_story, "Gull Chapel at dusk")
    out = style.postprocess(eval_story, unit, style_answer("pov_slip", "I rang the bell myself"))
    assert out.findings == [] and len(out.unverified) == 1
    real = style_answer("pov_slip", "I could hear the bell still humming", severity="critical")
    assert style.postprocess(eval_story, unit, real).findings[0].severity == "major"


def test_style_finding_for_an_undefined_setting_is_dropped(eval_story):
    story = replace(eval_story, style=StoryStyleConfig({"tense": "past"}, None))
    unit = style_unit(story, "Gull Chapel at dusk")
    out = style.postprocess(story, unit, style_answer("pov_slip", "I could hear the bell"))
    assert out.findings == [] and out.dropped == 1


# -- 2025 false positives (regression fixtures) -------------------------------------


def _regression(name: str):
    root = REGRESSIONS / name
    expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
    story = load_review_story(root / "src")
    unit = continuity_units(story, expected["passage_under_review"])[0]
    return story, unit, expected


@pytest.mark.parametrize("name", ["height-sitting-vs-standing", "sword-hand-after-fall"])
def test_regression_fixture_quotes_are_verbatim(name):
    story, _unit, expected = _regression(name)
    assert expected["expected_findings"] == 0
    for passage, quote in expected["quotes"].items():
        assert quote_found(quote, [story.content[passage]])


def _replay_2025_finding(story, unit, expected, quotes):
    p_name, other = expected["passage_under_review"], expected["other_passage"]
    data = answer(
        path_finding(
            story.ids[other],
            [(story.ids[p_name], quotes[p_name]), (story.ids[other], quotes[other])],
            finding_type=expected["type"],
        )
    )
    fake = FakeLLM({unit.tag: data})
    return continuity.review_unit(fake, story, unit)


def test_regression_head_near_half_again_her_height_sitting_vs_nearly_twice_standing():
    story, unit, expected = _regression("height-sitting-vs-standing")
    verbatim = _replay_2025_finding(story, unit, expected, expected["quotes"])
    assert len(verbatim.findings) == 1 and verbatim.unverified == []
    paraphrased = dict(expected["quotes"], **{"Day 5 EV": "its head was half her height"})
    out = _replay_2025_finding(story, unit, expected, paraphrased)
    assert out.findings == [] and len(out.unverified) == 1


def test_regression_sword_in_right_hand_vs_handle_against_left_ear_after_falling():
    story, unit, expected = _regression("sword-hand-after-fall")
    verbatim = _replay_2025_finding(story, unit, expected, expected["quotes"])
    assert len(verbatim.findings) == 1 and verbatim.unverified == []
    paraphrased = dict(expected["quotes"], **{"The fall": "the sword was now in her left hand"})
    out = _replay_2025_finding(story, unit, expected, paraphrased)
    assert out.findings == [] and len(out.unverified) == 1
