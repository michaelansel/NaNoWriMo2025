"""``nanoif bible extract``: flags, summary line and exit codes 0/1/2/3 (ADR-020)."""

from __future__ import annotations

import json

import pytest
from bible_helpers import WIDOW, CappedLLM, scripted, write_cache

from nanoif.cli import main


def extract(repo, *flags, client):
    return main(["bible", "extract", "--repo", str(repo), *flags], client=client)


@pytest.mark.intent("ADR-020")
def test_extract_writes_the_cache_and_the_diff_and_prints_one_summary_line(run_repo, capsys):
    assert extract(run_repo, client=scripted()) == 0
    out = capsys.readouterr().out
    assert "bible extract incremental: ok;" in out and "cache saved" in out and "$0.0000" in out
    assert (run_repo / "ai" / "story-bible-cache.json").is_file()
    diff = json.loads((run_repo / "dist" / "bible-diff.json").read_text(encoding="utf-8"))
    assert diff["status"] == "ok"
    assert extract(run_repo, client=scripted()) == 0
    assert "up_to_date" in capsys.readouterr().out


def test_dry_run_and_custom_paths(run_repo, tmp_path, capsys):
    cache = tmp_path / "elsewhere.json"
    diff = tmp_path / "diff.json"
    status = extract(run_repo, "--full", "--dry-run", "--cache", str(cache), "--diff-out", str(diff),
                     client=scripted())
    assert status == 0 and not cache.exists() and diff.is_file()
    assert "bible extract full: ok;" in capsys.readouterr().out


@pytest.mark.intent("ADR-020")
def test_partial_run_exits_3_and_names_the_failed_passage(run_repo, capsys):
    assert extract(run_repo, client=scripted(fail=(WIDOW,))) == 3
    out = capsys.readouterr().out
    assert f"not read: {WIDOW}: LLMTransportError" in out


@pytest.mark.intent("AC-story-bible-32", "ADR-020")
def test_spend_cap_exits_1_with_the_reason_and_writes_nothing(run_repo, capsys):
    assert extract(run_repo, client=CappedLLM([])) == 1
    err = capsys.readouterr().err
    assert "bible extract did not run: monthly AI spend cap reached: $10.00 of $10.00" in err
    assert "nothing was written" in err
    assert not (run_repo / "ai").exists() and not (run_repo / "dist").exists()


@pytest.mark.intent("AC-story-bible-2")
def test_invalid_cache_exits_1(run_repo, capsys):
    write_cache(run_repo, {"version": 2})
    assert extract(run_repo, client=scripted()) == 1
    assert "bible extract failed: Story Bible cache" in capsys.readouterr().err


def test_incremental_and_full_together_is_a_usage_error(run_repo):
    with pytest.raises(SystemExit) as info:
        extract(run_repo, "--incremental", "--full", client=scripted())
    assert info.value.code == 2
