"""Cache v2: load, validate, dangling references, atomic sorted write, diff (ADR-020)."""

from __future__ import annotations

import json

import pytest
from bible_helpers import CROSSING, DAY1, clone, small_cache

from nanoif.bible.cache import BibleCache, RetiredFact, diff_caches, load_cache, write_cache
from nanoif.errors import BibleCacheError, BuildError


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_missing_cache_is_none(tmp_path):
    assert load_cache(tmp_path / "ai" / "story-bible-cache.json") is None


def test_round_trip_keeps_every_field(tmp_path):
    path = _write(tmp_path / "cache.json", small_cache())
    cache = load_cache(path)
    assert isinstance(cache, BibleCache)
    assert cache.entities["tamsin-reeve"].aliases == ["Old Tam", "Tam"]
    assert cache.entities["pip-halloway"].facts[1].passage == "The widow's door"
    assert cache.conflicts["c-pip-halloway-1"].fact_ids == ["pip-halloway#1", "pip-halloway#2"]
    assert cache.to_dict() == small_cache()


@pytest.mark.intent("AC-story-bible-2", "ADR-020")
@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "not valid JSON"),
        ("[]", "not version 2"),
        (json.dumps({"categorized_facts": {}}), "not version 2"),
        (json.dumps({**small_cache(), "version": 1}), "not version 2"),
        (json.dumps({**small_cache(), "passages": []}), "schema"),
    ],
)
def test_unusable_cache_is_a_build_error(tmp_path, content, message):
    path = tmp_path / "cache.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(BibleCacheError, match=message) as info:
        load_cache(path)
    assert isinstance(info.value, BuildError)


@pytest.mark.intent("ADR-020")
@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["passages"][DAY1]["fact_ids"].append("tamsin-reeve#9"),
        lambda c: c["passages"][DAY1]["mentions"].append("maud-pellow"),
        lambda c: c["entities"]["tamsin-reeve"]["facts"][1].update(duplicate_of="tamsin-reeve#7"),
        lambda c: c["entities"]["tamsin-reeve"].update(merged_into="old-tam"),
        lambda c: c["conflicts"]["c-pip-halloway-1"].update(fact_ids=["pip-halloway#1", "pip-halloway#5"]),
        lambda c: c["conflicts"]["c-pip-halloway-1"].update(entity="wren-halloway"),
        lambda c: c["resolution"].update({"wren": "wren-halloway"}),
        lambda c: c["entities"]["pip-halloway"].update(next_n=2),
    ],
)
def test_dangling_reference_is_an_invalid_cache(tmp_path, mutate):
    data = clone(small_cache())
    mutate(data)
    with pytest.raises(BibleCacheError, match="dangling|next_n"):
        load_cache(_write(tmp_path / "cache.json", data))


@pytest.mark.intent("ADR-020")
def test_write_is_sorted_indented_with_a_trailing_newline(tmp_path):
    cache = BibleCache.from_dict(small_cache())
    target = tmp_path / "ai" / "story-bible-cache.json"
    write_cache(target, cache)
    text = target.read_text(encoding="utf-8")
    assert text == json.dumps(small_cache(), indent=2, sort_keys=True) + "\n"
    assert [p.name for p in target.parent.iterdir()] == ["story-bible-cache.json"]


@pytest.mark.intent("ADR-020")
def test_invalid_cache_is_never_written(tmp_path):
    target = tmp_path / "story-bible-cache.json"
    target.write_text("previous good cache\n", encoding="utf-8")
    cache = BibleCache.from_dict(small_cache())
    cache.passages[DAY1].fact_ids.append("tamsin-reeve#42")
    with pytest.raises(BibleCacheError, match="dangling"):
        write_cache(target, cache)
    assert target.read_text(encoding="utf-8") == "previous good cache\n"
    assert [p.name for p in tmp_path.iterdir()] == ["story-bible-cache.json"]


def test_diff_names_added_reworded_and_retired_facts_and_conflicts():
    old = BibleCache.from_dict(small_cache())
    new = BibleCache.from_dict(small_cache())
    tam = new.entities["tamsin-reeve"]
    tam.facts[0].claim = "Tam wears a grey braid"
    retired = tam.facts.pop(1)
    tam.retired.append(RetiredFact(retired.id, retired.claim, DAY1, "b" * 40, "passage_changed"))
    new.passages[DAY1].fact_ids.remove(retired.id)
    new.conflicts["c-pip-halloway-1"].status = "retired"
    marsh = new.entities["oriel-marsh"]
    marsh.facts.append(
        type(marsh.facts[0])("oriel-marsh#2", "Marsh keeps a ledger", "Marsh made a mark", CROSSING, "possession")
    )
    marsh.next_n = 3
    diff = diff_caches(old, new)
    assert diff["facts"] == {
        "added": ["oriel-marsh#2"],
        "reworded": ["tamsin-reeve#1"],
        "retired": ["tamsin-reeve#2"],
    }
    assert diff["conflicts"] == {"added": [], "retired": ["c-pip-halloway-1"]}
    assert diff["entities"] == {"added": [], "removed": [], "changed": ["oriel-marsh", "tamsin-reeve"]}


def test_diff_from_nothing_adds_everything():
    diff = diff_caches(None, BibleCache.from_dict(small_cache()))
    assert diff["entities"]["added"] == ["oriel-marsh", "pip-halloway", "river-wardens", "tamsin-reeve"]
    assert len(diff["facts"]["added"]) == 5
    assert diff["conflicts"]["added"] == ["c-pip-halloway-1"]
