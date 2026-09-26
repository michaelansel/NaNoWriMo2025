"""extract_bible: plan, spend check, extract, resolve, reconcile, save, diff (ADR-020)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from bible_helpers import (
    ANSWERS,
    CROSSING,
    DAY1,
    HOLLIN,
    PIP_CONFLICT,
    TEXTS,
    WIDOW,
    CappedLLM,
    commit,
    ent,
    scripted,
    write_story,
)

from nanoif.bible.cache import load_cache
from nanoif.bible.run import extract_bible
from nanoif.errors import BibleCacheError
from nanoif.llm.errors import LLMSpendCapReached
from nanoif.llm.fake import FakeLLM
from nanoif.schemas.artifacts import validate_artifact
from tests.conftest import git

NOW = datetime(2026, 11, 3, 7, 30, tzinfo=UTC)


@pytest.fixture
def repo(run_repo):
    return run_repo


def run(repo, client, mode="incremental", dry_run=False):
    return extract_bible(
        repo, mode, client, repo / "ai" / "story-bible-cache.json", dry_run,
        diff_out=repo / "dist" / "bible-diff.json", now=NOW,
    )


def extract_calls(client):
    return sorted(c.tag.split(":", 1)[1] for c in client.calls if c.tag.startswith("bible-extract:"))


def diff_file(repo):
    data = json.loads((repo / "dist" / "bible-diff.json").read_text(encoding="utf-8"))
    validate_artifact(data, "bible_diff")
    return data


@pytest.mark.intent("AC-story-bible-23", "ADR-020")
def test_first_run_builds_and_saves_the_cache(repo):
    client = scripted(reconcile=PIP_CONFLICT)
    outcome = run(repo, client)
    assert outcome.exit_code == 0 and outcome.status == "ok" and outcome.cache_written
    assert extract_calls(client) == sorted(TEXTS)
    cache = load_cache(repo / "ai" / "story-bible-cache.json")
    assert sorted(cache.entities) == ["oriel-marsh", "pip-halloway", "river-wardens", "tamsin-reeve"]
    tam = cache.entities["tamsin-reeve"]
    assert [f.id for f in tam.facts] == ["tamsin-reeve#1", "tamsin-reeve#2"]
    assert tam.aliases == ["Old Tam"] and tam.passages == [DAY1, CROSSING]
    day1 = cache.passages[DAY1]
    assert (day1.dropped.unverified_quote, day1.dropped.state, day1.dropped.generic_entity) == (1, 1, 1)
    assert day1.references[0].entity == "tamsin-reeve"
    assert cache.passages[WIDOW].fact_ids == ["pip-halloway#2"]
    assert cache.conflicts["c-pip-halloway-1"].fact_ids == ["pip-halloway#1", "pip-halloway#2"]
    assert cache.extraction.commit == git(repo, "rev-parse", "HEAD").strip()
    assert cache.extraction.extracted_at == "2026-11-03T07:30:00Z" and cache.extraction.mode == "incremental"
    diff = diff_file(repo)
    assert diff["status"] == "ok" and diff["base"] is None
    assert diff["passages_read"] == sorted(TEXTS)
    assert diff["conflicts"]["added"] == ["c-pip-halloway-1"]
    assert "facts" in outcome.summary and "$" in outcome.summary


@pytest.mark.intent("AC-story-bible-17")
def test_nothing_changed_means_no_model_call_and_no_write(repo):
    run(repo, scripted())
    path = repo / "ai" / "story-bible-cache.json"
    before = path.read_text(encoding="utf-8")
    client = scripted()
    outcome = run(repo, client)
    assert client.calls == []
    assert outcome.status == "up_to_date" and outcome.exit_code == 0 and not outcome.cache_written
    assert path.read_text(encoding="utf-8") == before
    assert diff_file(repo)["status"] == "up_to_date"


@pytest.mark.intent("AC-story-bible-17", "AC-story-bible-20")
def test_only_changed_passages_are_re_read_and_ids_survive(repo):
    run(repo, scripted(reconcile=PIP_CONFLICT))
    write_story(repo, {**TEXTS, HOLLIN: TEXTS[HOLLIN] + " He was dry."})
    commit(repo)
    answers = {**ANSWERS, HOLLIN: {
        "summary": "Pip is twelve and dry.",
        "entities": [ent("Pip Halloway", [
            ("Pip Halloway is twelve years old", "Wren's brother was twelve", "trait"),
            ("Pip is dry", "He was dry.", "trait"),
        ])],
        "references": [],
    }}
    client = scripted(answers)
    outcome = run(repo, client)
    assert extract_calls(client) == [HOLLIN]
    assert outcome.cache_written
    pip = load_cache(repo / "ai" / "story-bible-cache.json").entities["pip-halloway"]
    assert [(f.id, f.claim) for f in pip.facts] == [
        ("pip-halloway#1", "Pip Halloway is twelve years old"),
        ("pip-halloway#2", "Pip is eleven"),
        ("pip-halloway#3", "Pip is dry"),
    ]
    diff = diff_file(repo)
    assert diff["facts"] == {"added": ["pip-halloway#3"], "reworded": ["pip-halloway#1"], "retired": []}
    assert diff["base"]["extracted_at"] == "2026-11-03T07:30:00Z"


@pytest.mark.intent("AC-story-bible-20", "AC-story-bible-15")
def test_deleted_passage_retires_its_facts_and_conflicts_without_a_model_call(repo):
    run(repo, scripted(reconcile=PIP_CONFLICT))
    write_story(repo, {k: v for k, v in TEXTS.items() if k != WIDOW})
    commit(repo)
    client = scripted()
    outcome = run(repo, client)
    assert extract_calls(client) == []
    cache = load_cache(repo / "ai" / "story-bible-cache.json")
    assert WIDOW not in cache.passages
    pip = cache.entities["pip-halloway"]
    assert [(f.id, f.reason) for f in pip.retired] == [("pip-halloway#2", "passage_deleted")]
    assert WIDOW not in pip.passages
    assert cache.conflicts["c-pip-halloway-1"].status == "retired"
    assert outcome.cache_written and diff_file(repo)["passages_deleted"] == [WIDOW]


@pytest.mark.intent("ADR-020")
def test_a_passage_that_fails_twice_is_left_unrecorded_and_the_run_is_partial(repo):
    client = scripted(fail=(WIDOW,))
    outcome = run(repo, client)
    assert outcome.exit_code == 3 and outcome.status == "partial" and outcome.cache_written
    assert extract_calls(client).count(WIDOW) == 2
    cache = load_cache(repo / "ai" / "story-bible-cache.json")
    assert WIDOW not in cache.passages and HOLLIN in cache.passages
    failed = diff_file(repo)["passages_failed"]
    assert [f["passage"] for f in failed] == [WIDOW] and "LLMTransportError" in failed[0]["reason"]


@pytest.mark.intent("ADR-020")
def test_failed_reconcile_leaves_entities_pending_and_the_run_partial(repo):
    outcome = run(repo, scripted(reconcile=FakeLLM.transport_error()))
    assert outcome.exit_code == 3
    cache = load_cache(repo / "ai" / "story-bible-cache.json")
    assert cache.entities["pip-halloway"].reconcile == "pending"
    assert cache.entities["river-wardens"].reconcile == "done"
    assert [p["entity"] for p in diff_file(repo)["pending"]] == ["Pip Halloway", "Tamsin Reeve"]


@pytest.mark.intent("AC-story-bible-32", "ADR-020")
def test_spend_cap_stops_the_run_before_any_call_and_nothing_is_saved(repo):
    client = CappedLLM([])
    with pytest.raises(LLMSpendCapReached):
        run(repo, client)
    assert client.calls == [] and client.estimates[0] > 0
    assert not (repo / "ai").exists() and not (repo / "dist" / "bible-diff.json").exists()


@pytest.mark.intent("AC-story-bible-32")
def test_a_run_halted_part_way_saves_nothing(repo):
    run(repo, scripted())
    path = repo / "ai" / "story-bible-cache.json"
    before = path.read_text(encoding="utf-8")
    write_story(repo, {k: v + " More." for k, v in TEXTS.items()})
    commit(repo)
    with pytest.raises(LLMSpendCapReached):
        run(repo, scripted(halt_on=HOLLIN))
    assert path.read_text(encoding="utf-8") == before


@pytest.mark.intent("ADR-020")
def test_dry_run_writes_only_the_diff(repo):
    outcome = run(repo, scripted(), dry_run=True)
    assert not outcome.cache_written and not (repo / "ai").exists()
    diff = diff_file(repo)
    assert diff["dry_run"] and not diff["cache_written"]
    assert "oriel-marsh" in diff["entities"]["added"]


@pytest.mark.intent("AC-story-bible-2")
def test_invalid_cache_fails_the_run_and_saves_nothing(repo):
    path = repo / "ai" / "story-bible-cache.json"
    path.parent.mkdir()
    path.write_text('{"version": 1}', encoding="utf-8")
    client = scripted()
    with pytest.raises(BibleCacheError):
        run(repo, client)
    assert client.calls == [] and path.read_text(encoding="utf-8") == '{"version": 1}'


@pytest.mark.intent("AC-story-bible-20")
def test_full_mode_re_reads_every_passage_and_keeps_ids(repo):
    run(repo, scripted(reconcile=PIP_CONFLICT))
    before = load_cache(repo / "ai" / "story-bible-cache.json")
    client = scripted(reconcile=PIP_CONFLICT)
    outcome = run(repo, client, mode="full")
    assert extract_calls(client) == sorted(TEXTS)
    assert not outcome.cache_written
    assert diff_file(repo)["facts"] == {"added": [], "reworded": [], "retired": []}
    assert before.entities["pip-halloway"].facts == load_cache(repo / "ai" / "story-bible-cache.json").entities["pip-halloway"].facts
