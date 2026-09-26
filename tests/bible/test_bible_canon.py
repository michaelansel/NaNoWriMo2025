"""The canon pack and per-passage retrieval for the Continuity Editor (ADR-020)."""

from __future__ import annotations

import json

import pytest
from bible_helpers import CROSSING, DAY1, HOLLIN, TEXTS, WIDOW, clone, fact, small_cache

from nanoif.bible.assemble import assemble
from nanoif.bible.cache import BibleCache
from nanoif.bible.canon import (
    MAX_FACTS_PER_ENTITY,
    MAX_FACTS_PER_UNIT,
    CanonFact,
    build_canon_pack,
    load_canon_pack,
    select_canon,
)
from nanoif.check.overrides import Overrides
from nanoif.errors import ArtifactValidationError, BuildError
from nanoif.schemas.artifacts import validate_artifact
from nanoif.twee.passages import content_hash

HASHES = {name: content_hash(text) for name, text in TEXTS.items()}
PIN = f'pin: River Wardens = The River Wardens fly a green pennant | "the green pennant of the River Wardens" @ {CROSSING}\n'


def pack(overrides="", cache=None):
    data = BibleCache.from_dict(cache if cache is not None else small_cache())
    bible = assemble(data, Overrides.from_text(overrides), HASHES, texts=TEXTS)
    result = build_canon_pack(bible)
    validate_artifact(result, "canon_pack")
    return result


def entry(result, slug):
    return next(e for e in result["entities"] if e["slug"] == slug)


def test_pack_holds_entities_facts_conflicts_and_alias_index():
    result = pack("intentional-conflict: c-pip-halloway-1\n")
    assert result["source"] == {"commit": "a" * 40, "extracted_at": "2026-11-02T08:00:00Z", "cache_present": True}
    assert result["passages"] == dict(sorted(HASHES.items()))
    tam = entry(result, "tamsin-reeve")
    assert tam["facts"][0] == {
        "id": "tamsin-reeve#2",
        "claim": "Tamsin Reeve has carried the lantern for forty years",
        "quote": "every working day of those forty years",
        "passage": DAY1,
        "pinned": False,
    }
    assert result["conflicts"] == [
        {
            "id": "c-pip-halloway-1",
            "fact_ids": ["pip-halloway#1", "pip-halloway#2"],
            "intentional": True,
            "label": "c-pip-halloway-1",
        }
    ]
    index = result["alias_index"]
    assert index["tamsin reeve"] == index["old tam"] == index["tam"] == "tamsin-reeve"
    assert index["captain marsh"] == "oriel-marsh"
    assert "pip" in index


@pytest.mark.intent("ADR-020")
def test_pack_keeps_six_facts_pinned_first_then_evidence_then_newest():
    data = clone(small_cache())
    marsh = data["entities"]["oriel-marsh"]
    marsh["facts"] = [
        fact(f"oriel-marsh#{n}", f"Marsh fact {n}", "Captain Oriel Marsh stood in the stern", CROSSING)
        for n in range(1, 9)
    ]
    marsh["facts"][7]["duplicate_of"] = "oriel-marsh#2"
    marsh["next_n"] = 9
    data["passages"][CROSSING]["fact_ids"] = [f["id"] for f in marsh["facts"]]
    result = pack(f'pin: Marsh = Marsh is the captain | "Captain Oriel Marsh" @ {CROSSING}\n', cache=data)
    ids = [f["id"] for f in entry(result, "oriel-marsh")["facts"]]
    assert len(ids) == MAX_FACTS_PER_ENTITY == 6
    assert ids[0].startswith("oriel-marsh#pin-")
    assert ids[1:] == ["oriel-marsh#2", "oriel-marsh#7", "oriel-marsh#6", "oriel-marsh#5", "oriel-marsh#4"]


def test_pack_without_cache_says_so():
    result = build_canon_pack(assemble(None, Overrides(), HASHES))
    validate_artifact(result, "canon_pack")
    assert result["source"]["cache_present"] is False
    assert result["entities"] == [] and result["alias_index"] == {}


def test_alias_index_leaves_out_short_forms_pronouns_and_ambiguous_names():
    data = clone(small_cache())
    data["entities"]["pip-halloway"]["aliases"] = ["Pip", "Pi", "him"]
    data["entities"]["oriel-marsh"]["aliases"] = ["Captain Marsh", "Pip"]
    index = pack(cache=data)["alias_index"]
    assert "pi" not in index and "him" not in index
    assert "pip" not in index
    assert index["pip halloway"] == "pip-halloway"


def test_select_matches_longest_first_on_word_boundaries_in_order_of_first_mention():
    text = "Captain Marsh nodded. Old Tam laughed; Tamsinette did not. Pipkin ran."
    result = select_canon(pack(), "The toll", text, HASHES)
    assert result.entities == ("oriel-marsh", "tamsin-reeve")
    assert [f.entity for f in result.facts] == ["Oriel Marsh", "Tamsin Reeve", "Tamsin Reeve"]
    assert result.facts[0] == CanonFact(
        "oriel-marsh#1", "Oriel Marsh", "Oriel Marsh is a captain", CROSSING,
        "Captain Oriel Marsh stood in the stern",
    )


@pytest.mark.intent("AC-story-bible-28")
def test_select_leaves_out_facts_of_the_passage_under_review_and_stale_facts():
    changed = {**HASHES, HOLLIN: "f" * 16}
    result = select_canon(pack(), WIDOW, "Pip Halloway and Old Tam", changed)
    assert [f.id for f in result.facts] == ["tamsin-reeve#2", "tamsin-reeve#1"]
    assert result.own_excluded == 1 and result.stale_excluded == 1


@pytest.mark.intent("AC-story-bible-21")
def test_pinned_facts_are_exempt_from_the_cap():
    data = clone(small_cache())
    tam = data["entities"]["tamsin-reeve"]
    tam["facts"] = [fact(f"tamsin-reeve#{n}", f"Tam fact {n}", "her grey braid", DAY1) for n in range(1, 7)]
    tam["next_n"] = 7
    data["passages"][DAY1]["fact_ids"] = [f["id"] for f in tam["facts"]]
    result_pack = pack(PIN, cache=data)
    many = []
    for n in range(8):
        extra = clone(result_pack["entities"][0])
        extra["slug"] = f"warden-{n}"
        extra["facts"] = [dict(f, id=f"warden-{n}#{i}", pinned=False, passage=DAY1) for i, f in
                          enumerate(entry(result_pack, "tamsin-reeve")["facts"], start=1)]
        result_pack["alias_index"][f"warden {n}"] = extra["slug"]
        many.append(extra)
    result_pack["entities"] = many + result_pack["entities"]
    text = " ".join(f"warden {n}" for n in range(8)) + " and the River Wardens."
    result = select_canon(result_pack, "The toll", text, HASHES)
    pinned = [f for f in result.facts if f.pinned]
    assert [f.entity for f in pinned] == ["River Wardens"]
    assert len(result.facts) == MAX_FACTS_PER_UNIT + 1 == 41
    assert result.capped == 8


def test_load_canon_pack_missing_or_invalid_is_an_error(tmp_path):
    with pytest.raises(BuildError, match="canon_pack not found"):
        load_canon_pack(tmp_path / "canon-pack.json")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": 1}), encoding="utf-8")
    with pytest.raises(ArtifactValidationError):
        load_canon_pack(bad)
    good = tmp_path / "canon-pack.json"
    good.write_text(json.dumps(pack()), encoding="utf-8")
    assert load_canon_pack(good)["version"] == 1
