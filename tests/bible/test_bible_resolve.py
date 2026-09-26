"""Stage 2, resolve: exact names first, then at most one batched model call (ADR-020)."""

from __future__ import annotations

import pytest
from bible_helpers import small_cache

from nanoif.bible.cache import BibleCache, Dropped
from nanoif.bible.extract import ExtractedEntity, ExtractedFact, PassageExtraction
from nanoif.bible.resolve import RESOLVE_TAG, resolve
from nanoif.bible.source import SourcePassage
from nanoif.check.overrides import Overrides
from nanoif.llm.errors import LLMSpendCapReached
from nanoif.llm.fake import FakeLLM


def extraction(name, *entities):
    passage = SourcePassage(name, "src/EV-20261101.twee", "text", "0" * 16)
    return PassageExtraction(passage, "", tuple(entities), (), Dropped())


def ent(name, etype="character", aliases=(), claims=()):
    facts = tuple(ExtractedFact(claim, claim, "trait") for claim in claims)
    return ExtractedEntity(name, etype, tuple(aliases), None, facts)


def cache():
    return BibleCache.from_dict(small_cache())


def test_known_names_resolve_without_a_model_call():
    client = FakeLLM([])
    out = resolve(
        client,
        [extraction("Day 3 EV", ent("Old Tam"), ent("the Pip Halloway", aliases=["Pip"]))],
        cache(),
        Overrides(),
    )
    assert out.assignments == {("Day 3 EV", 0): "tamsin-reeve", ("Day 3 EV", 1): "pip-halloway"}
    assert out.new_entities == {} and client.calls == []


@pytest.mark.intent("AC-story-bible-14", "ADR-020")
def test_alias_override_merges_names_under_the_canonical_name_without_a_call():
    overrides = Overrides.from_text("alias: Weir House = the old mill\n")
    client = FakeLLM([])
    out = resolve(
        client,
        [
            extraction("Hollin Reach", ent("the old mill", "location", claims=["The mill is old"])),
            extraction("Day 2 EV", ent("Weir House", "location")),
        ],
        None,
        overrides,
    )
    (key,) = out.new_entities
    assert out.new_entities[key].name == "Weir House"
    assert out.new_entities[key].aliases == ("the old mill",)
    assert set(out.assignments.values()) == {key}
    assert client.calls == []


@pytest.mark.intent("AC-story-bible-14", "ADR-020")
def test_not_entity_override_removes_the_entity():
    overrides = Overrides.from_text("not-entity: the man who built the weir\n")
    out = resolve(
        FakeLLM([]),
        [extraction("The widow's door", ent("The man who built the weir"))],
        None,
        overrides,
    )
    assert out.assignments == {("The widow's door", 0): None}
    assert out.new_entities == {}


def test_names_shared_across_passages_form_one_cluster():
    client = FakeLLM({RESOLVE_TAG: {"merges": [], "drop": []}})
    out = resolve(
        client,
        [
            extraction("Day 1 EV", ent("Wren Halloway", aliases=["Wren"])),
            extraction("The weir", ent("Wren", claims=["Wren counts to two hundred"])),
        ],
        None,
        Overrides(),
    )
    (key,) = out.new_entities
    assert out.new_entities[key].name == "Wren Halloway"
    assert out.assignments == {("Day 1 EV", 0): key, ("The weir", 0): key}
    (call,) = client.calls
    assert call.reasoning_effort == "medium"
    assert "NEW k1 (character): Wren Halloway | Wren" in call.user


@pytest.mark.intent("ADR-020")
def test_only_high_confidence_same_type_merges_apply_and_each_key_once():
    answer = {
        "merges": [
            {"into": "tamsin-reeve", "members": ["k1"], "confidence": "high"},
            {"into": "k2", "members": ["k3"], "confidence": "medium"},
            {"into": "k4", "members": ["k2"], "confidence": "high"},
            {"into": "pip-halloway", "members": ["k1"], "confidence": "high"},
        ],
        "drop": [{"key": "k5", "reason": "not_named"}, {"key": "tamsin-reeve", "reason": "generic"}],
    }
    client = FakeLLM({RESOLVE_TAG: answer})
    out = resolve(
        client,
        [
            extraction(
                "Back at the ferry",
                ent("Tamsin Reave", claims=["Tamsin Reave poled the river for thirty years"]),
                ent("Maud Pellow"),
                ent("Maud's stew", "item"),
                ent("brass lantern", "item"),
                ent("the man"),
            )
        ],
        cache(),
        Overrides(),
    )
    a = out.assignments
    assert a[("Back at the ferry", 0)] == "tamsin-reeve"
    assert a[("Back at the ferry", 1)] == "k2" and a[("Back at the ferry", 2)] == "k3"
    assert a[("Back at the ferry", 3)] == "k4"
    assert a[("Back at the ferry", 4)] is None
    assert set(out.new_entities) == {"k2", "k3", "k4"}
    assert out.merges == [{"into": "tamsin-reeve", "members": ["Tamsin Reave"]}]
    assert out.dropped == [{"names": ["the man"], "reason": "not_named"}]
    assert "EXISTING tamsin-reeve (character): Tamsin Reeve | Old Tam | Tam" in client.calls[0].user


def test_new_cluster_merged_into_another_new_cluster_becomes_its_alias():
    answer = {"merges": [{"into": "k1", "members": ["k2"], "confidence": "high"}], "drop": []}
    out = resolve(
        FakeLLM({RESOLVE_TAG: answer}),
        [extraction("The chapel path", ent("Brother Ilex")), extraction("Day 1 EV", ent("the bell-ringer"))],
        None,
        Overrides(),
    )
    assert out.new_entities["k1"].aliases == ("the bell-ringer",)
    assert set(out.assignments.values()) == {"k1"}


@pytest.mark.intent("ADR-020")
def test_failed_resolve_call_creates_the_entities_pending():
    client = FakeLLM({RESOLVE_TAG: [FakeLLM.transport_error(), FakeLLM.transport_error()]})
    out = resolve(client, [extraction("Day 1 EV", ent("Maud Pellow"))], None, Overrides())
    assert len(client.calls) == 2
    assert out.failed is not None and "LLMTransportError" in out.failed
    assert [e.pending for e in out.new_entities.values()] == [True]


def test_halt_is_raised():
    halt = LLMSpendCapReached("cap", reason="monthly AI spend cap reached", month_usd=10, cap_usd=10)
    with pytest.raises(LLMSpendCapReached):
        resolve(FakeLLM({RESOLVE_TAG: halt}), [extraction("Day 1 EV", ent("Maud Pellow"))], None, Overrides())


def test_world_entity_resolves_to_the_reserved_key():
    out = resolve(FakeLLM([]), [extraction("Day 1 EV", ent("World", "world"))], None, Overrides())
    assert out.assignments == {("Day 1 EV", 0): "world"}
    assert out.new_entities["world"].type == "world"
