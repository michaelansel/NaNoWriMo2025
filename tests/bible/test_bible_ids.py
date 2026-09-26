"""Names, slugs and ids of the Story Bible (ADR-020)."""

import hashlib

import pytest

from nanoif.bible.cache import Entity, Fact
from nanoif.bible.extract import ExtractedFact
from nanoif.bible.ids import (
    WORLD_SLUG,
    assign_fact_ids,
    claim_overlap,
    entity_slug,
    is_generic_name,
    normalize_name,
    pin_fact_id,
    retire_passage_facts,
    slugify,
)


def test_normalize_name_drops_article_possessive_case_and_punctuation():
    assert normalize_name("The Widow Kestle") == "widow kestle"
    assert normalize_name("  Maud Pellow’s ") == "maud pellow"
    assert normalize_name("Old  Tam") == "old tam"
    assert normalize_name("the wardens' ledger") == "wardens ledger"
    assert normalize_name("A lantern") == "lantern"


def test_slugify():
    assert slugify("Tamsin Reeve") == "tamsin-reeve"
    assert slugify("the wardens' ledger") == "the-wardens-ledger"
    assert slugify("???") == "entity"


@pytest.mark.intent("ADR-020")
def test_entity_slug_suffixes_on_collision_and_reserves_world():
    assert entity_slug("Tamsin Reeve", set()) == "tamsin-reeve"
    assert entity_slug("Tamsin Reeve", {"tamsin-reeve"}) == "tamsin-reeve-2"
    assert entity_slug("Tamsin Reeve", {"tamsin-reeve", "tamsin-reeve-2"}) == "tamsin-reeve-3"
    assert entity_slug("World", set()) == f"{WORLD_SLUG}-2"


@pytest.mark.intent("ADR-020")
def test_pin_fact_id_is_entity_slug_and_claim_hash():
    claim = "The River Wardens fly a green pennant"
    digest = hashlib.sha256(claim.encode("utf-8")).hexdigest()[:8]
    assert pin_fact_id("river-wardens", claim) == f"river-wardens#pin-{digest}"


@pytest.mark.intent("AC-story-bible-23")
@pytest.mark.parametrize(
    ("name", "generic"),
    [
        ("no one", True),
        ("Thirteen people", True),
        ("some of the wardens", True),
        ("every warden", True),
        ("4 wardens", True),
        ("the twelve", True),
        ("Noah", False),
        ("Old Tam", False),
        ("Oneida", False),
        ("the man", False),
    ],
)
def test_generic_names_start_with_a_quantifier_or_number(name, generic):
    assert is_generic_name(name) is generic


def test_claim_overlap_is_symmetric_over_content_tokens():
    assert claim_overlap("Tam has a grey braid", "Tam has a grey braid") == 1.0
    assert claim_overlap("Pip is twelve", "Pip is twelve years old") == pytest.approx(2 / 4)
    assert claim_overlap("", "Pip") == 0.0


# -- fact ids across re-extraction ----------------------------------------------------

P = "Hollin Reach"
C1 = "c" * 40
C2 = "d" * 40


def pip():
    return Entity(
        slug="pip-halloway",
        name="Pip Halloway",
        type="character",
        next_n=4,
        facts=[
            Fact("pip-halloway#1", "Pip is twelve", "Wren's brother was twelve", P, "trait"),
            Fact("pip-halloway#2", "Pip has a key", "pulled a key from inside his shirt", P, "possession"),
            Fact("pip-halloway#3", "Pip went with the fish carts", "with the fish carts", "Day 1 EV", "event"),
        ],
    )


@pytest.mark.intent("AC-story-bible-20", "ADR-020")
def test_same_quote_keeps_the_id_and_a_reworded_claim_keeps_it_too():
    entity = pip()
    result = assign_fact_ids(
        entity,
        P,
        [
            ExtractedFact("Pip Halloway is twelve years old", "Wren’s brother  was twelve", "trait"),
            ExtractedFact("Pip has the key", "a key from inside his shirt", "possession"),
        ],
        C1,
    )
    assert result.kept == ["pip-halloway#1", "pip-halloway#2"]
    assert result.reworded == ["pip-halloway#1", "pip-halloway#2"]
    assert result.added == [] and result.retired == []
    assert entity.fact("pip-halloway#1").claim == "Pip Halloway is twelve years old"
    assert entity.next_n == 4


@pytest.mark.intent("AC-story-bible-20", "ADR-020")
def test_unmatched_facts_retire_and_new_ones_never_reuse_an_id():
    entity = pip()
    shivering = ExtractedFact("Pip is shivering with bravado", "shivering under his bravado", "trait")
    result = assign_fact_ids(entity, P, [shivering], C1)
    assert result.added == ["pip-halloway#4"] and entity.next_n == 5
    assert result.retired == ["pip-halloway#1", "pip-halloway#2"]
    assert [f.id for f in entity.retired] == ["pip-halloway#1", "pip-halloway#2"]
    assert entity.retired[0].reason == "passage_changed" and entity.retired[0].retired_commit == C1
    assert [f.id for f in entity.facts] == ["pip-halloway#3", "pip-halloway#4"]
    twelve = ExtractedFact("Pip is twelve", "Wren's brother was twelve", "trait")
    again = assign_fact_ids(entity, P, [shivering, twelve], C2)
    assert again.kept == ["pip-halloway#4"] and again.added == ["pip-halloway#5"]


def test_claim_overlap_below_threshold_is_a_new_fact():
    entity = pip()
    result = assign_fact_ids(entity, P, [ExtractedFact("Pip is dry on the jetty", "he was dry", "trait")], C1)
    assert result.added == ["pip-halloway#4"]


def test_facts_of_other_passages_are_untouched_and_duplicate_links_to_retired_facts_clear():
    entity = pip()
    entity.facts[2].duplicate_of = "pip-halloway#1"
    retired = retire_passage_facts(entity, P, C1, "passage_deleted")
    assert retired == ["pip-halloway#1", "pip-halloway#2"]
    assert [f.id for f in entity.facts] == ["pip-halloway#3"]
    assert entity.facts[0].duplicate_of is None
    assert {f.reason for f in entity.retired} == {"passage_deleted"}
