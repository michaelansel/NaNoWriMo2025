"""The stage-1 extraction store: keys, sharded entries, atomic writes, accounting (ADR-026)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nanoif.bible.store import (
    STORE_DIR_ENV,
    ExtractStore,
    StoreKey,
    bypassed_report,
    resolve_store_dir,
)
from nanoif.llm.prompts import prompt_hash, schema_hash
from nanoif.schemas.artifacts import validate_artifact

ANSWER = {
    "summary": "Tam is up before Wren.",
    "entities": [
        {
            "name": "Tamsin Reeve",
            "type": "character",
            "aliases": ["Old Tam"],
            "role": "ferry keeper",
            "facts": [{"claim": "Tam has a grey braid", "quote": "her grey braid", "kind": "trait"}],
        }
    ],
    "references": [],
}
NOW = datetime(2026, 11, 3, 7, 30, tzinfo=UTC)


def key(name: str = "Day 1 EV", **changes) -> StoreKey:
    fields = {
        "passage_name": name,
        "content_hash": "c" * 16,
        "profile": "fake",
        "model": "fake-model",
        "reasoning_effort": "low",
        "max_tokens": 12_000,
        **changes,
    }
    return StoreKey.build(**fields)


def store(directory: Path, **kwargs) -> ExtractStore:
    return ExtractStore.open(directory, clock=lambda: NOW, **kwargs)


def entry_path(directory: Path, k: StoreKey) -> Path:
    return directory / k.digest[:2] / f"{k.digest}.json"


@pytest.mark.intent("ADR-026")
def test_the_key_is_the_sha256_of_the_canonical_key_fields():
    k = key()
    fields = k.fields()
    assert sorted(fields) == sorted([
        "passage_name", "content_hash", "prompt_hash", "schema_hash", "profile", "model",
        "reasoning_effort", "max_tokens",
    ])
    assert fields["prompt_hash"] == prompt_hash("bible_extract")
    assert fields["schema_hash"] == schema_hash("bible_extract")
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert k.digest == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@pytest.mark.intent("ADR-026", "AC-story-bible-36")
def test_every_key_field_changes_the_key_but_nothing_else_is_in_it():
    base = key().digest
    for change in (
        {"name": "The crossing"},
        {"content_hash": "d" * 16},
        {"profile": "exe"},
        {"model": "other-model"},
        {"reasoning_effort": "medium"},
        {"max_tokens": 16_000},
    ):
        assert key(**change).digest != base, change
    assert key().digest == base


@pytest.mark.intent("ADR-026")
def test_a_saved_answer_is_a_hit_on_the_same_key(tmp_path):
    s = store(tmp_path / "store", run="4242")
    k = key()
    assert s.save(k, ANSWER)
    path = entry_path(tmp_path / "store", k)
    entry = json.loads(path.read_text(encoding="utf-8"))
    validate_artifact(entry, "extract_store_entry")
    assert entry == {
        "version": 1,
        "key_fields": k.fields(),
        "answer": ANSWER,
        "created_at": "2026-11-03T07:30:00Z",
        "run": "4242",
    }
    assert [p.name for p in path.parent.iterdir()] == [path.name]
    assert s.lookup(k) == ANSWER
    assert s.lookup(key(content_hash="d" * 16)) is None
    assert s.report() == {
        "status": "used", "hits": ["Day 1 EV"], "misses": 1, "invalid": 0, "write_failed": 0,
        "reason": "",
    }
    assert s.warnings == []


def test_a_new_store_reads_what_an_earlier_one_wrote(tmp_path):
    store(tmp_path / "store").save(key(), ANSWER)
    later = store(tmp_path / "store")
    assert later.lookup(key()) == ANSWER and later.report()["hits"] == ["Day 1 EV"]


@pytest.mark.parametrize(
    ("damage", "why"),
    [
        (lambda p, e: p.write_text("{not json", encoding="utf-8"), "not valid JSON"),
        (lambda p, e: p.write_text(json.dumps({**e, "version": 2}), encoding="utf-8"), "schema"),
        (
            lambda p, e: p.write_text(
                json.dumps({**e, "key_fields": {**e["key_fields"], "model": "other"}}),
                encoding="utf-8",
            ),
            "key fields",
        ),
        (
            lambda p, e: p.write_text(
                json.dumps({**e, "answer": {"summary": "no entities"}}), encoding="utf-8"
            ),
            "bible_extract",
        ),
        (lambda p, e: (p.unlink(), p.mkdir()), "cannot be read"),
    ],
    ids=["corrupt", "schema", "other-key", "answer-schema", "unreadable"],
)
@pytest.mark.intent("ADR-026")
def test_an_unusable_entry_is_a_miss_counted_invalid_with_a_warning_naming_it(
    tmp_path, damage, why
):
    s = store(tmp_path / "store")
    k = key()
    s.save(k, ANSWER)
    path = entry_path(tmp_path / "store", k)
    damage(path, json.loads(path.read_text(encoding="utf-8")))
    assert s.lookup(k) is None
    assert s.report() == {
        "status": "used", "hits": [], "misses": 1, "invalid": 1, "write_failed": 0, "reason": "",
    }
    assert len(s.warnings) == 1 and str(path) in s.warnings[0] and why in s.warnings[0]


@pytest.mark.intent("ADR-026")
def test_a_failed_write_is_counted_warned_and_never_raises(tmp_path):
    s = store(tmp_path / "store")
    k = key()
    (tmp_path / "store" / k.digest[:2]).write_text("a file where the shard should be")
    assert s.save(k, ANSWER) is False
    assert s.report()["write_failed"] == 1 and s.report()["status"] == "used"
    assert "Day 1 EV" in s.warnings[0] and k.digest[:2] in s.warnings[0]


def test_an_answer_that_is_not_json_is_a_failed_write(tmp_path):
    s = store(tmp_path / "store")
    assert s.save(key(), {"summary": object()}) is False
    assert s.report()["write_failed"] == 1


@pytest.mark.intent("ADR-026")
def test_an_unusable_directory_makes_the_store_unavailable_and_every_lookup_a_miss(tmp_path):
    blocker = tmp_path / "state"
    blocker.write_text("not a directory")
    s = store(blocker / "extract-store")
    assert s.lookup(key()) is None
    assert s.save(key(), ANSWER) is False
    report = s.report()
    assert report["status"] == "unavailable" and report["misses"] == 1
    assert report["hits"] == [] and report["write_failed"] == 0
    assert str(blocker / "extract-store") in report["reason"]


def test_the_directory_is_created_when_missing(tmp_path):
    directory = tmp_path / "a" / "b" / "extract-store"
    s = store(directory)
    assert directory.is_dir() and s.report()["status"] == "used"


def test_a_store_not_read_reports_bypassed_with_the_reason(tmp_path):
    s = store(tmp_path / "store")
    s.save(key(), ANSWER)
    report = s.report(read=False, reason="--full re-reads every passage")
    assert report == {
        "status": "bypassed", "hits": [], "misses": 0, "invalid": 0, "write_failed": 0,
        "reason": "--full re-reads every passage",
    }
    assert bypassed_report("no store")["status"] == "bypassed"


def test_the_directory_comes_from_the_environment_or_the_state_directory(tmp_path):
    assert resolve_store_dir({STORE_DIR_ENV: str(tmp_path / "x")}) == tmp_path / "x"
    assert resolve_store_dir({"XDG_STATE_HOME": str(tmp_path)}) == (
        tmp_path / "nanoif" / "extract-store"
    )
    assert resolve_store_dir({}) == Path.home() / ".local" / "state" / "nanoif" / "extract-store"


def test_tests_never_touch_the_real_store(isolated_extract_store):
    assert resolve_store_dir() == isolated_extract_store
    assert str(Path.home() / ".local") not in str(isolated_extract_store)
