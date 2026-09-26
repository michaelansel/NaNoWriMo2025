"""Stage 3, reconcile: duplicates and conflicts by fact id, checked by code (ADR-020)."""

from __future__ import annotations

import pytest
from bible_helpers import small_cache

from nanoif.bible.cache import BibleCache, Fact
from nanoif.bible.reconcile import reconcile, reconcile_tag
from nanoif.llm.errors import LLMBudgetExceeded
from nanoif.llm.fake import FakeLLM


def entities():
    cache = BibleCache.from_dict(small_cache())
    pip = cache.entities["pip-halloway"]
    pip.facts.append(Fact("pip-halloway#3", "Pip is Wren's brother", "Wren's brother", "Hollin Reach", "relationship"))
    pip.next_n = 4
    return [cache.entities["tamsin-reeve"], pip, cache.entities["oriel-marsh"]]


def verdict(slug, duplicates=(), conflicts=()):
    return {
        "slug": slug,
        "duplicates": [list(group) for group in duplicates],
        "conflicts": [{"a": a, "b": b, "note": note} for a, b, note in conflicts],
    }


@pytest.mark.intent("AC-story-bible-13", "ADR-020")
def test_valid_answer_is_applied_per_entity():
    answer = {
        "entities": [
            verdict("tamsin-reeve"),
            verdict("pip-halloway", conflicts=[("pip-halloway#1", "pip-halloway#2", "twelve or eleven")]),
        ]
    }
    client = FakeLLM({reconcile_tag(1): answer})
    results = reconcile(client, entities())
    (call,) = client.calls
    assert call.reasoning_effort == "medium"
    assert "- pip-halloway#2 [The widow's door] Pip is eleven" in call.user
    assert "Eleven years old" not in call.user
    assert "oriel-marsh" not in call.user
    assert results["pip-halloway"].ok
    assert results["pip-halloway"].conflicts == (("pip-halloway#1", "pip-halloway#2", "twelve or eleven"),)
    assert results["tamsin-reeve"].ok and results["tamsin-reeve"].duplicates == ()
    assert results["oriel-marsh"].ok and results["oriel-marsh"].conflicts == ()


@pytest.mark.intent("ADR-020")
@pytest.mark.parametrize(
    ("pip", "reason"),
    [
        (verdict("pip-halloway", duplicates=[["pip-halloway#1", "tamsin-reeve#1"]]), "not a fact of"),
        (verdict("pip-halloway", duplicates=[["pip-halloway#1", "pip-halloway#9"]]), "not a fact of"),
        (
            verdict("pip-halloway", duplicates=[["pip-halloway#1", "pip-halloway#2"], ["pip-halloway#2", "pip-halloway#3"]]),
            "two duplicate groups",
        ),
        (
            verdict(
                "pip-halloway",
                duplicates=[["pip-halloway#1", "pip-halloway#2"]],
                conflicts=[("pip-halloway#1", "pip-halloway#2", "x")],
            ),
            "pairs two duplicates",
        ),
        (verdict("pip-halloway", conflicts=[("pip-halloway#1", "pip-halloway#1", "x")]), "with itself"),
        (None, "missing"),
    ],
)
def test_invalid_answer_leaves_only_that_entity_pending(pip, reason):
    answer = {"entities": [verdict("tamsin-reeve")] + ([pip] if pip else [])}
    results = reconcile(FakeLLM({reconcile_tag(1): answer}), entities())
    assert not results["pip-halloway"].ok and reason in results["pip-halloway"].error
    assert results["tamsin-reeve"].ok


def test_failed_call_leaves_the_batch_pending_after_one_re_attempt():
    client = FakeLLM({reconcile_tag(1): [FakeLLM.transport_error(), FakeLLM.truncated()]})
    results = reconcile(client, entities())
    assert len(client.calls) == 2
    assert not results["pip-halloway"].ok and "LLMTruncatedError" in results["pip-halloway"].error
    assert results["oriel-marsh"].ok


def test_halt_is_raised():
    halt = LLMBudgetExceeded("budget", spent=1, budget=1, projected=2)
    with pytest.raises(LLMBudgetExceeded):
        reconcile(FakeLLM({reconcile_tag(1): halt}), entities())


def test_batches_stay_under_the_input_budget():
    many = []
    for n in range(12):
        cache = BibleCache.from_dict(small_cache())
        pip = cache.entities["pip-halloway"]
        pip.slug = f"pip-{n}"
        pip.facts = [
            Fact(f"pip-{n}#{i}", "Pip " + "is very much a boy " * 40, "q", "Hollin Reach", "trait")
            for i in range(1, 11)
        ]
        many.append(pip)
    client = FakeLLM(lambda call: {"entities": [verdict(s) for s in _slugs(call.user)]})
    results = reconcile(client, many)
    assert len(client.calls) > 1
    assert all((len(call.system) + len(call.user)) // 4 <= 8000 for call in client.calls)
    assert all(result.ok for result in results.values()) and len(results) == 12


def _slugs(user):
    return [line.split()[1].rstrip(":") for line in user.splitlines() if line.startswith("ENTITY ")]
