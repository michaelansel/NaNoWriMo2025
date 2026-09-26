"""Stage 1, extract: one model call per passage, then code keeps only what it can verify."""

from __future__ import annotations

import pytest

from nanoif.bible.extract import (
    EXTRACT_MAX_TOKENS,
    ExtractedFact,
    RosterEntry,
    extract_passage,
    extract_tag,
)
from nanoif.bible.source import SourcePassage
from nanoif.llm.fake import FakeLLM
from nanoif.llm.prompts import prompt_schema
from nanoif.twee.passages import content_hash

TEXT = (
    "Wren had carried two copper bits. Captain Oriel Marsh stood in the stern with one boot on "
    "the gunwale, the way he always stood. The fog lay on the river like wool. \"Corvin Ashby "
    "still owes the wardens the spring toll,\" he said, to no one in particular. "
    "Thirteen people have drowned at that weir. [[Hollin Reach]]"
)
PASSAGE = SourcePassage("The crossing", "src/EV-20261101.twee", TEXT, content_hash(TEXT))


def answer(entities=(), references=(), summary="Wren pays the toll."):
    return {"summary": summary, "entities": list(entities), "references": list(references)}


def ent(name, etype="character", aliases=(), role=None, facts=()):
    return {"name": name, "type": etype, "aliases": list(aliases), "role": role, "facts": list(facts)}


def fct(claim, quote, kind="trait"):
    return {"claim": claim, "quote": quote, "kind": kind}


def run(data, roster=(), not_entities=()):
    client = FakeLLM({extract_tag(PASSAGE.name): data})
    return client, extract_passage(client, PASSAGE, list(roster), list(not_entities))


@pytest.mark.intent("ADR-020")
def test_calls_the_model_once_with_low_effort_and_the_extract_schema():
    roster = [RosterEntry("Oriel Marsh", "character", ("Captain Marsh",))]
    client, _ = run(answer(), roster, ["the man who built the weir"])
    (call,) = client.calls
    assert call.tag == "bible-extract:The crossing"
    assert call.reasoning_effort == "low" and call.max_tokens == EXTRACT_MAX_TOKENS == 12000
    assert call.schema == prompt_schema("bible_extract")
    assert TEXT in call.user and TEXT not in call.system
    assert "- Oriel Marsh (character), also: Captain Marsh" in call.user
    assert "- the man who built the weir" in call.user


@pytest.mark.intent("AC-story-bible-10", "ADR-020")
def test_fact_with_a_quote_not_in_the_passage_is_dropped_and_counted():
    marsh = ent(
        "Oriel Marsh",
        aliases=["Captain Marsh", "he"],
        facts=[
            fct("Oriel Marsh is a captain", "Captain Oriel Marsh stood in the stern", "relationship"),
            fct("Marsh has a scar", "a scar ran down his cheek"),
            fct("Marsh always stands with a boot on the gunwale", "“one boot on  the gunwale”"),
        ],
    )
    _, out = run(answer([marsh]))
    (entity,) = out.entities
    assert [f.claim for f in entity.facts] == [
        "Oriel Marsh is a captain",
        "Marsh always stands with a boot on the gunwale",
    ]
    assert entity.facts[1] == ExtractedFact(
        "Marsh always stands with a boot on the gunwale", "one boot on  the gunwale", "trait"
    )
    assert entity.aliases == ("Captain Marsh",)
    assert out.dropped.unverified_quote == 1


@pytest.mark.intent("AC-story-bible-11", "ADR-020")
def test_state_facts_are_dropped_and_counted():
    wren = ent(
        "Wren Halloway",
        facts=[
            fct("The fog lies on the river", "The fog lay on the river like wool.", "state"),
            fct("Wren has two copper bits", "Wren had carried two copper bits.", "possession"),
        ],
    )
    _, out = run(answer([wren]))
    assert [f.kind for f in out.entities[0].facts] == ["possession"]
    assert out.dropped.state == 1


@pytest.mark.intent("AC-story-bible-9", "ADR-020")
def test_entities_named_with_a_quantifier_or_number_are_dropped_and_counted():
    _, out = run(
        answer(
            [
                ent("no one", facts=[fct("No one listens", "to no one in particular")]),
                ent("Thirteen people", "group", facts=[fct("drowned", "Thirteen people have drowned")]),
                ent("Corvin Ashby", facts=[fct("Corvin owes the toll", "Corvin Ashby")]),
            ]
        )
    )
    assert [e.name for e in out.entities] == ["Corvin Ashby"]
    assert out.dropped.generic_entity == 2
    assert out.dropped.unverified_quote == 0


def test_same_entity_twice_in_one_answer_is_merged():
    _, out = run(
        answer(
            [
                ent("Oriel Marsh", facts=[fct("a", "Captain Oriel Marsh stood in the stern")]),
                ent("the Oriel Marsh", aliases=["Marsh"], role="warden captain",
                    facts=[fct("b", "the way he always stood")]),
            ]
        )
    )
    (entity,) = out.entities
    assert [f.claim for f in entity.facts] == ["a", "b"]
    assert entity.aliases == ("Marsh",) and entity.role == "warden captain"


def test_world_entity_is_named_world():
    _, out = run(answer([ent("the river", "world", facts=[fct("r", "The fog lay on the river")])]))
    assert out.entities[0].name == "World" and out.entities[0].type == "world"


@pytest.mark.intent("AC-story-bible-12")
def test_references_are_verified_and_capped_at_twenty():
    refs = [{"quote": "the way he always stood", "pronoun": "he", "entity": "Oriel Marsh"}] * 22
    refs += [{"quote": "she said nothing", "pronoun": "she", "entity": None}]
    _, out = run(answer(references=refs))
    assert len(out.references) == 20
    assert out.references[0].entity == "Oriel Marsh"
    assert out.dropped.unverified_quote == 1


def test_summary_is_kept():
    _, out = run(answer(summary="  Wren pays the toll.  "))
    assert out.summary == "Wren pays the toll."
    assert out.passage is PASSAGE


def test_model_failure_is_raised_not_swallowed():
    client = FakeLLM({extract_tag(PASSAGE.name): FakeLLM.transport_error()})
    from nanoif.llm.errors import LLMTransportError

    with pytest.raises(LLMTransportError):
        extract_passage(client, PASSAGE, [], [])
