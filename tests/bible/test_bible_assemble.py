"""Stage 4, assemble: cache + overrides + current hashes -> the Bible, no model (ADR-020)."""

from __future__ import annotations

import pytest
from bible_helpers import CROSSING, DAY1, HOLLIN, TEXTS, WIDOW, clone, small_cache

from nanoif.bible.assemble import assemble
from nanoif.bible.cache import BibleCache
from nanoif.bible.ids import pin_fact_id
from nanoif.check.overrides import Overrides
from nanoif.twee.passages import content_hash

HASHES = {name: content_hash(text) for name, text in TEXTS.items()}


def bible(overrides="", cache=None, hashes=None, **kwargs):
    data = BibleCache.from_dict(cache if cache is not None else small_cache())
    return assemble(data, Overrides.from_text(overrides), hashes or HASHES, texts=TEXTS, **kwargs)


def names(entities):
    return [entity.name for entity in entities]


def named(entities, name):
    return next(entity for entity in entities if entity.name == name)


def test_sections_by_type_and_facts_with_quotes():
    result = bible()
    assert names(result.cast) == ["Oriel Marsh", "Pip Halloway", "Tamsin Reeve"]
    assert names(result.groups) == ["River Wardens"]
    assert result.places == () and result.items == ()
    tam = named(result.cast, "Tamsin Reeve")
    assert tam.aliases == ("Old Tam", "Tam") and tam.role == "ferry keeper"
    assert tam.passages == (DAY1, CROSSING)
    assert [(f.id, f.quote, f.passage) for f in tam.facts][0] == ("tamsin-reeve#1", "her grey braid", DAY1)


@pytest.mark.intent("AC-story-bible-14")
def test_alias_override_merges_entities_under_the_canonical_name():
    data = clone(small_cache())
    data["entities"]["tamsin-reeve"]["aliases"] = []
    data["entities"]["old-tam"] = {
        **clone(data["entities"]["river-wardens"]),
        "slug": "old-tam",
        "name": "Old Tam",
        "type": "character",
        "passages": [CROSSING],
    }
    data["resolution"]["old tam"] = "old-tam"
    result = bible("alias: Tamsin Reeve = Old Tam, Tam\n", cache=data)
    assert names(result.cast) == ["Oriel Marsh", "Pip Halloway", "Tamsin Reeve"]
    tam = named(result.cast, "Tamsin Reeve")
    assert tam.slug == "tamsin-reeve" and tam.aliases == ("Old Tam", "Tam")
    assert tam.passages == (DAY1, CROSSING)


@pytest.mark.intent("AC-story-bible-14")
def test_not_entity_override_removes_the_entity():
    result = bible("not-entity: Captain Marsh\n")
    assert "Oriel Marsh" not in names(result.cast)
    assert result.unmatched == ()


@pytest.mark.intent("AC-story-bible-14", "AC-story-bible-21")
def test_pin_shows_the_fact_with_its_quote_and_passage_first():
    claim = "The River Wardens fly a green pennant"
    result = bible(f'pin: River Wardens = {claim} | "The green pennant of the River Wardens" @ {CROSSING}\n')
    (wardens,) = result.groups
    (pinned,) = wardens.facts
    assert pinned.id == pin_fact_id("river-wardens", claim) and pinned.pinned
    assert pinned.quote == "The green pennant of the River Wardens" and pinned.passage == CROSSING
    assert pinned.quote_found


def test_pin_whose_quote_is_not_found_is_flagged_and_still_shown():
    result = bible(f'pin: Pip Halloway = Pip is twelve | "Pip was twelve" @ {HOLLIN}\n')
    pip = named(result.cast, "Pip Halloway")
    assert pip.facts[0].pinned and not pip.facts[0].quote_found


def test_override_lines_that_match_nothing_are_listed():
    result = bible(
        "alias: Maud Pellow = Maud\nnot-entity: no one\n"
        f'pin: Wren Halloway = Wren is seventeen | "seventeenth spring" @ {DAY1}\n'
        "intentional-conflict: c-oriel-marsh-4\n"
    )
    assert [line for line, _text in result.unmatched] == [1, 2, 3, 4]


@pytest.mark.intent("AC-story-bible-13")
def test_open_conflicts_are_listed_with_both_quotes():
    (conflict,) = bible().conflicts
    assert conflict.id == "c-pip-halloway-1" and conflict.intentional is None
    assert [f.quote for f in conflict.facts] == ["Wren's brother was twelve", "Eleven years old"]
    assert [f.passage for f in conflict.facts] == [HOLLIN, WIDOW]


@pytest.mark.intent("AC-story-bible-13", "ADR-020")
@pytest.mark.parametrize(
    "line",
    [
        "intentional-conflict: c-pip-halloway-1",
        "intentional-conflict: pip-age = Pip | eleven years",
    ],
)
def test_intentional_conflict_moves_to_intentional_mysteries(line):
    result = bible(line + "\n")
    assert result.conflicts == ()
    (mystery,) = result.mysteries
    assert mystery.label in {"c-pip-halloway-1", "pip-age"}
    assert [c.id for c in mystery.conflicts] == ["c-pip-halloway-1"]
    assert result.intentional_facts() == {
        "pip-halloway#1": mystery.label,
        "pip-halloway#2": mystery.label,
    }


def test_mystery_whose_fragment_matches_no_conflict_is_unmatched():
    result = bible("intentional-conflict: mystery = Pip Halloway | never anyone's wife\n")
    assert len(result.conflicts) == 1 and result.mysteries == ()
    assert [line for line, _ in result.unmatched] == [1]


def test_world_rules_collect_rule_facts_from_any_entity():
    data = clone(small_cache())
    data["entities"]["tamsin-reeve"]["facts"][1]["kind"] = "rule"
    result = bible(cache=data)
    assert [(entity, fact.id) for entity, fact in result.world_rules] == [("Tamsin Reeve", "tamsin-reeve#2")]
    assert [f.id for f in named(result.cast, "Tamsin Reeve").facts] == ["tamsin-reeve#1"]


def test_duplicates_fold_under_their_representative():
    data = clone(small_cache())
    data["entities"]["tamsin-reeve"]["facts"][1]["duplicate_of"] = "tamsin-reeve#1"
    tam = named(bible(cache=data).cast, "Tamsin Reeve")
    assert [(f.id, f.evidence, f.restatements) for f in tam.facts] == [
        ("tamsin-reeve#1", 2, ("tamsin-reeve#2",))
    ]


@pytest.mark.intent("AC-story-bible-15")
def test_freshness_lists_changed_new_and_deleted_passages():
    hashes = {**HASHES, HOLLIN: "f" * 16, "The toll": "e" * 16}
    del hashes[WIDOW]
    result = bible(hashes=hashes, extraction_result="failure")
    fresh = result.freshness
    assert fresh.commit == "a" * 40 and fresh.extracted_at == "2026-11-02T08:00:00Z"
    assert fresh.changed == (HOLLIN,) and fresh.new == ("The toll",) and fresh.deleted == (WIDOW,)
    assert fresh.unread == (HOLLIN, "The toll")
    assert fresh.extraction_result == "failure"


@pytest.mark.intent("AC-story-bible-1")
def test_no_cache_is_a_placeholder_with_every_passage_unread():
    result = assemble(None, Overrides(), HASHES)
    assert not result.cache_present and result.passage_count == 4
    assert result.entities == () and result.freshness.new == tuple(sorted(HASHES))


def test_pending_entities_are_named_in_freshness():
    data = clone(small_cache())
    data["entities"]["pip-halloway"]["reconcile"] = "pending"
    assert bible(cache=data).freshness.pending == ("Pip Halloway",)
