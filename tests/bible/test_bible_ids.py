"""Names, slugs and ids of the Story Bible (ADR-020)."""

import hashlib

import pytest

from nanoif.bible.ids import (
    WORLD_SLUG,
    claim_overlap,
    entity_slug,
    is_generic_name,
    normalize_name,
    pin_fact_id,
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


@pytest.mark.intent("AC-story-bible-9")
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
