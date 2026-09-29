"""``bible extract --preview --cache-out``: the pull request's would-be cache (ADR-026)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from bible_helpers import (
    ANSWERS,
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
from nanoif.errors import BibleError
from nanoif.schemas.artifacts import validate_artifact

NOW = datetime(2026, 11, 3, 7, 30, tzinfo=UTC)
NEW_WIDOW = TEXTS[WIDOW] + " Hollis Crane waited on the jetty."
WIDOW_ANSWER = {
    "summary": "Pip is eleven; Hollis waits.",
    "entities": [
        ent("Pip", [("Pip is eleven", "Eleven years old", "trait"),
                    ("Pip left the house", "Pip had gone", "event")]),
        ent("Hollis Crane", [("Hollis waits on the jetty", "Hollis Crane waited on the jetty", "event")]),
    ],
    "references": [],
}


@pytest.fixture
def merged(run_repo):
    """``main`` extracted, then the pull request changes The widow's door."""
    extract_bible(run_repo, "incremental", scripted(reconcile=PIP_CONFLICT),
                  run_repo / "ai" / "story-bible-cache.json", False, now=NOW)
    write_story(run_repo, {**TEXTS, WIDOW: NEW_WIDOW})
    commit(run_repo)
    return run_repo


def preview(repo, client, out, store=None):
    return extract_bible(
        repo, "incremental", client, repo / "ai" / "story-bible-cache.json", True,
        diff_out=repo / "dist" / "bible-diff.json", now=NOW, store=store, preview=True,
        cache_out=out,
    )


def tags(client, prefix):
    return [c.tag for c in client.calls if c.tag.startswith(prefix)]


@pytest.mark.intent("AC-story-bible-33", "ADR-026")
def test_preview_writes_the_would_be_cache_and_never_ai(merged, tmp_path):
    ai_cache = merged / "ai" / "story-bible-cache.json"
    before = ai_cache.read_text(encoding="utf-8")
    client = scripted({**ANSWERS, WIDOW: WIDOW_ANSWER})
    out = tmp_path / "preview" / "story-bible-cache.json"
    outcome = preview(merged, client, out, ExtractStore.open(tmp_path / "store"))
    assert outcome.exit_code == 0 and not outcome.cache_written
    assert ai_cache.read_text(encoding="utf-8") == before
    assert tags(client, "bible-extract:") == [f"bible-extract:{WIDOW}"]
    assert tags(client, "bible-reconcile") == []
    cache = load_cache(out)
    assert cache.passages[WIDOW].content_hash != load_cache(ai_cache).passages[WIDOW].content_hash
    hollis = [e for e in cache.entities.values() if e.name == "Hollis Crane"]
    assert len(hollis) == 1 and hollis[0].facts[0].passage == WIDOW
    assert cache.conflicts == load_cache(ai_cache).conflicts
    diff = json.loads((merged / "dist" / "bible-diff.json").read_text(encoding="utf-8"))
    validate_artifact(diff, "bible_diff")
    assert diff["dry_run"] and diff["passages_read"] == [WIDOW]
    assert diff["store"]["status"] == "used" and diff["store"]["misses"] == 1
    assert "preview" in outcome.summary


@pytest.mark.intent("AC-story-bible-35", "ADR-026")
def test_a_failed_passage_stays_unread_in_the_preview_cache(merged, tmp_path):
    write_story(merged, {**TEXTS, WIDOW: NEW_WIDOW, HOLLIN: TEXTS[HOLLIN] + " He was dry."})
    commit(merged)
    out = tmp_path / "preview.json"
    outcome = preview(merged, scripted({**ANSWERS, WIDOW: WIDOW_ANSWER}, fail=(HOLLIN,)), out)
    assert outcome.exit_code == 3 and outcome.status == "partial"
    cache = load_cache(out)
    assert cache.passages[HOLLIN].content_hash == load_cache(
        merged / "ai" / "story-bible-cache.json").passages[HOLLIN].content_hash
    assert [f["passage"] for f in outcome.diff["passages_failed"]] == [HOLLIN]


def test_preview_with_nothing_to_read_calls_no_model(run_repo, tmp_path):
    extract_bible(run_repo, "incremental", scripted(), run_repo / "ai" / "story-bible-cache.json",
                  False, now=NOW)
    client = scripted()
    outcome = preview(run_repo, client, tmp_path / "preview.json")
    assert client.calls == [] and outcome.status == "up_to_date"
    assert load_cache(tmp_path / "preview.json") == load_cache(
        run_repo / "ai" / "story-bible-cache.json")


def test_the_dry_run_still_reconciles(merged):
    client = scripted({**ANSWERS, WIDOW: WIDOW_ANSWER}, reconcile=PIP_CONFLICT)
    extract_bible(merged, "incremental", client, merged / "ai" / "story-bible-cache.json", True,
                  now=NOW)
    assert tags(client, "bible-reconcile")


def test_preview_refuses_to_write_over_the_saved_cache(merged):
    with pytest.raises(BibleError, match="ai/"):
        preview(merged, scripted(), merged / "ai" / "story-bible-cache.json")


def test_preview_needs_incremental_mode(merged, tmp_path):
    with pytest.raises(BibleError, match="incremental"):
        extract_bible(merged, "full", scripted(), merged / "ai" / "story-bible-cache.json", True,
                      preview=True, cache_out=tmp_path / "p.json")


@pytest.mark.intent("AC-story-bible-33", "ADR-026")
def test_the_cli_preview_writes_the_cache_out_and_the_diff(merged, tmp_path, capsys):
    out = tmp_path / "preview.json"
    status = main(["bible", "extract", "--repo", str(merged), "--preview", "--cache-out", str(out),
                   "--diff-out", str(tmp_path / "diff.json")],
                  client=scripted({**ANSWERS, WIDOW: WIDOW_ANSWER}))
    assert status == 0
    printed = capsys.readouterr().out
    assert f"Wrote {out}" in printed and "ai/story-bible-cache.json" not in printed
    assert load_cache(out) is not None and (tmp_path / "diff.json").is_file()


@pytest.mark.parametrize(
    "flags",
    [["--preview"], ["--cache-out", "x.json"], ["--preview", "--full", "--cache-out", "x.json"]],
    ids=["no-cache-out", "no-preview", "full"],
)
def test_the_cli_preview_flags_go_together(merged, flags, capsys):
    client = scripted()
    try:
        status = main(["bible", "extract", "--repo", str(merged), *flags], client=client)
    except SystemExit as exc:
        status = exc.code
    assert status == 2 and client.calls == []
    assert "--preview" in capsys.readouterr().err

