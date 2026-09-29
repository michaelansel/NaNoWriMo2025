"""extract_bible with the extraction store: reads, writes, spend and reporting (ADR-026)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from bible_helpers import (
    ANSWERS,
    DAY1,
    HOLLIN,
    PIP_CONFLICT,
    TEXTS,
    WIDOW,
    commit,
    ent,
    scripted,
    write_story,
)

from nanoif.bible.cache import load_cache
from nanoif.bible.run import extract_bible
from nanoif.bible.store import ExtractStore
from nanoif.cli import main
from nanoif.llm.fake import FakeLLM
from nanoif.schemas.artifacts import validate_artifact

NOW = datetime(2026, 11, 3, 7, 30, tzinfo=UTC)


@pytest.fixture
def repo(run_repo):
    return run_repo


@pytest.fixture
def store_dir(tmp_path):
    return tmp_path / "extract-store"


def run(repo, client, store, mode="incremental", dry_run=False, cache=None):
    return extract_bible(
        repo, mode, client, cache or repo / "ai" / "story-bible-cache.json", dry_run,
        diff_out=repo / "dist" / "bible-diff.json", now=NOW, store=store,
    )


def extract_calls(client):
    return sorted(c.tag.split(":", 1)[1] for c in client.calls if c.tag.startswith("bible-extract:"))


def diff_file(repo):
    data = json.loads((repo / "dist" / "bible-diff.json").read_text(encoding="utf-8"))
    validate_artifact(data, "bible_diff")
    return data


def entries(directory):
    return sorted(directory.glob("*/*.json")) if directory.is_dir() else []


class EstimatingLLM(FakeLLM):
    """A scripted fake that records every spend estimate and never refuses."""

    def check_spend(self, estimate_usd: float = 0.0) -> None:
        self.estimates = [*getattr(self, "estimates", []), estimate_usd]


@pytest.mark.intent("ADR-026")
def test_a_run_saves_every_answer_it_paid_for(repo, store_dir):
    outcome = run(repo, scripted(), ExtractStore.open(store_dir))
    assert len(entries(store_dir)) == len(TEXTS)
    assert outcome.diff["store"] == {
        "status": "used", "hits": [], "misses": len(TEXTS), "invalid": 0, "write_failed": 0,
        "reason": "",
    }
    assert diff_file(repo)["store"]["status"] == "used"


@pytest.mark.intent("ADR-026", "AC-story-bible-17")
def test_a_hit_makes_no_model_call_and_filters_the_stored_answer_again(repo, store_dir):
    run(repo, scripted(), ExtractStore.open(store_dir), dry_run=True)
    reference = scripted(reconcile=PIP_CONFLICT)
    run(repo, reference, None, cache=repo / "reference.json")
    client = scripted(reconcile=PIP_CONFLICT)
    outcome = run(repo, client, ExtractStore.open(store_dir))
    assert extract_calls(client) == []
    assert [c.tag for c in client.calls][0] == "bible-resolve"
    assert outcome.diff["store"]["hits"] == sorted(TEXTS)
    assert outcome.diff["passages_read"] == sorted(TEXTS)
    cache = load_cache(repo / "ai" / "story-bible-cache.json")
    day1 = cache.passages[DAY1].dropped
    assert (day1.unverified_quote, day1.state, day1.generic_entity) == (1, 1, 1)
    expected = load_cache(repo / "reference.json")
    assert cache.entities == expected.entities and cache.conflicts == expected.conflicts
    assert "4 hit(s)" in outcome.summary and DAY1 in outcome.summary


@pytest.mark.intent("ADR-026")
def test_the_spend_estimate_counts_misses_only(repo, store_dir):
    cold = scripted(cls=EstimatingLLM)
    run(repo, cold, ExtractStore.open(store_dir), dry_run=True)
    warm = scripted(cls=EstimatingLLM)
    run(repo, warm, ExtractStore.open(store_dir), dry_run=True)
    write_story(repo, {**TEXTS, HOLLIN: TEXTS[HOLLIN] + " He was dry."})
    commit(repo)
    one = scripted(cls=EstimatingLLM)
    run(repo, one, ExtractStore.open(store_dir), dry_run=True)
    assert extract_calls(warm) == [] and extract_calls(one) == [HOLLIN]
    assert warm.estimates[0] < one.estimates[0] < cold.estimates[0]


@pytest.mark.intent("ADR-026")
def test_full_never_reads_the_store_but_writes_it(repo, store_dir):
    run(repo, scripted(), ExtractStore.open(store_dir), dry_run=True)
    hollin = [p for p in entries(store_dir) if HOLLIN in p.read_text(encoding="utf-8")]
    assert len(hollin) == 1
    hollin[0].unlink()
    answers = {**ANSWERS, HOLLIN: {"summary": "Pip is twelve, again.", "entities": [
        ent("Pip Halloway", [("Pip is twelve", "Wren's brother was twelve", "trait")])
    ], "references": []}}
    client = scripted(answers)
    outcome = run(repo, client, ExtractStore.open(store_dir), mode="full", dry_run=True)
    assert extract_calls(client) == sorted(TEXTS)
    store = outcome.diff["store"]
    assert store["status"] == "bypassed" and store["hits"] == [] and "--full" in store["reason"]
    assert len(entries(store_dir)) == len(TEXTS)
    assert "Pip is twelve, again." in hollin[0].read_text(encoding="utf-8")
    later = scripted()
    run(repo, later, ExtractStore.open(store_dir), dry_run=True)
    assert extract_calls(later) == []


@pytest.mark.intent("ADR-026")
def test_a_library_call_without_a_store_neither_reads_nor_writes(repo, isolated_extract_store):
    outcome = run(repo, scripted(), None)
    assert outcome.diff["store"]["status"] == "bypassed"
    assert not isolated_extract_store.exists()


@pytest.mark.intent("ADR-026")
def test_an_invalid_entry_is_extracted_again_and_warned(repo, store_dir):
    run(repo, scripted(), ExtractStore.open(store_dir), dry_run=True)
    first = entries(store_dir)[0]
    first.write_text("{broken", encoding="utf-8")
    client = scripted()
    outcome = run(repo, client, ExtractStore.open(store_dir), dry_run=True)
    assert len(extract_calls(client)) == 1
    assert outcome.diff["store"]["invalid"] == 1 and outcome.diff["store"]["misses"] == 1
    assert any(str(first) in w for w in outcome.warnings)
    assert json.loads(first.read_text(encoding="utf-8"))["version"] == 1


@pytest.mark.intent("ADR-026")
def test_an_unavailable_store_costs_money_not_correctness(repo, tmp_path):
    (tmp_path / "blocker").write_text("not a directory")
    client = scripted()
    outcome = run(repo, client, ExtractStore.open(tmp_path / "blocker" / "store"))
    assert extract_calls(client) == sorted(TEXTS) and outcome.exit_code == 0
    assert outcome.diff["store"]["status"] == "unavailable"
    assert "store unavailable" in outcome.summary


@pytest.mark.intent("AC-story-bible-36", "ADR-026")
def test_after_merge_a_passage_the_pull_request_read_is_not_sent_again(repo, store_dir):
    run(repo, scripted(reconcile=PIP_CONFLICT), ExtractStore.open(store_dir))
    ids_before = load_cache(repo / "ai" / "story-bible-cache.json").live_fact_ids()
    write_story(repo, {**TEXTS, WIDOW: TEXTS[WIDOW] + " Nobody saw him go."})
    commit(repo)
    pull_request = scripted()
    run(repo, pull_request, ExtractStore.open(store_dir), dry_run=True)
    assert extract_calls(pull_request) == [WIDOW]
    assert load_cache(repo / "ai" / "story-bible-cache.json").live_fact_ids() == ids_before
    # The merge also brings an override that changes the roster sent to the model.
    (repo / "story-overrides.txt").write_text("alias: Pip Halloway = Wren's brother\n")
    commit(repo)
    main_run = scripted(reconcile=PIP_CONFLICT)
    outcome = run(repo, main_run, ExtractStore.open(store_dir))
    assert extract_calls(main_run) == []
    assert outcome.diff["store"]["hits"] == [WIDOW] and outcome.cache_written
    cache = load_cache(repo / "ai" / "story-bible-cache.json")
    assert cache.passages[WIDOW].fact_ids == ["pip-halloway#2"]


@pytest.mark.intent("ADR-026")
def test_the_cli_reads_and_writes_the_default_store(repo, isolated_extract_store, capsys):
    args = ["bible", "extract", "--repo", str(repo), "--dry-run"]
    assert main(args, client=scripted()) == 0
    assert len(entries(isolated_extract_store)) == len(TEXTS)
    capsys.readouterr()
    entries(isolated_extract_store)[0].write_text("{broken", encoding="utf-8")
    assert main(args, client=scripted()) == 0
    out = capsys.readouterr().out
    assert "store used: 3 hit(s)" in out
    assert "::warning::extraction store entry" in out


@pytest.mark.intent("ADR-026")
def test_the_cli_full_run_writes_but_does_not_read(repo, isolated_extract_store, capsys):
    assert main(["bible", "extract", "--repo", str(repo), "--dry-run"], client=scripted()) == 0
    client = scripted()
    assert main(["bible", "extract", "--repo", str(repo), "--full", "--dry-run"],
                client=client) == 0
    assert extract_calls(client) == sorted(TEXTS)
    assert "store bypassed" in capsys.readouterr().out
