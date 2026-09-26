"""The /extract-story-bible sticky comment (<!-- nano:bible -->), dry run or did not run."""

from __future__ import annotations

import json

import pytest
from github_fakes import API, REPO

import nanoif.github.cli as github_cli
from nanoif.cli import main
from nanoif.github.api import GitHubAPI
from nanoif.github.bible import render_bible_diff, render_bible_not_run
from nanoif.github.comments import MARKER_BIBLE, MARKERS
from nanoif.github.report import RunInfo

RUN = RunInfo(run_id="42", url="https://example.invalid/runs/42")


def diff(**overrides):
    data = {
        "status": "ok",
        "mode": "incremental",
        "dry_run": True,
        "cache_written": False,
        "base": {"commit": "a" * 40, "extracted_at": "2026-11-02T08:00:00Z"},
        "passages_read": ["Hollin Reach", "The widow's door"],
        "passages_failed": [],
        "passages_deleted": [],
        "pending": [],
        "entities": {"added": ["pip-halloway"], "removed": [], "changed": ["tamsin-reeve"]},
        "facts": {"added": ["pip-halloway#1", "pip-halloway#2"], "reworded": ["tamsin-reeve#1"],
                  "retired": ["tamsin-reeve#3"]},
        "conflicts": {"added": ["c-pip-halloway-1"], "retired": []},
        "usage": {"calls": 3, "usd": 0.0123, "usd_known": True, "profile": "exe",
                  "model": "gpt-oss-120b"},
    }
    data.update(overrides)
    return data


@pytest.mark.intent("AC-story-bible-31")
def test_dry_run_comment_lists_what_would_change_and_the_cost():
    body = render_bible_diff(diff(), RUN)
    assert body.startswith(MARKER_BIBLE)
    assert "### Story Bible: dry run: nothing was saved" in body
    assert "2 passages read" in body and "3 calls" in body and "$0.0123" in body
    assert "exe (gpt-oss-120b)" in body and "[run #42](https://example.invalid/runs/42)" in body
    assert "**Entities:** 1 added (pip-halloway), 1 changed (tamsin-reeve), 0 removed" in body
    assert "**Facts:** 2 added, 1 reworded, 1 retired" in body
    assert "**Conflicts:** 1 added (c-pip-halloway-1), 0 retired" in body
    assert "Compared with the saved extraction of 2026-11-02 (aaaaaaaa)" in body
    assert "MARKER" not in body


@pytest.mark.intent("AC-story-bible-31")
def test_dry_run_comment_names_passages_that_could_not_be_read():
    body = render_bible_diff(
        diff(status="partial", passages_failed=[{"passage": "The weir", "reason": "LLMTransportError: down"}],
             pending=[{"entity": "Pip Halloway", "reason": "reconcile failed"}]),
        RUN,
    )
    assert "dry run: nothing was saved" in body
    assert "*The weir*: LLMTransportError: down" in body
    assert "*Pip Halloway*: reconcile failed" in body


def test_dry_run_comment_with_nothing_to_read_says_no_model_was_called():
    body = render_bible_diff(
        diff(status="up_to_date", passages_read=[], entities={"added": [], "removed": [], "changed": []},
             facts={"added": [], "reworded": [], "retired": []}, conflicts={"added": [], "retired": []},
             usage={"calls": 0, "usd": 0.0, "usd_known": True}),
        RUN,
    )
    assert "No passage changed since the saved extraction, so nothing was read and no model was called." in body


@pytest.mark.intent("AC-story-bible-31", "AC-story-bible-32")
def test_did_not_run_comment_gives_the_reason_and_no_earlier_result():
    reason = "monthly AI spend cap reached: $10.00 of $10.00 in 2026-11 (resets 2026-12-01 UTC)"
    body = render_bible_not_run(reason, RUN)
    assert body.startswith(MARKER_BIBLE)
    assert "### Story Bible: did not run" in body
    assert reason in body and "Nothing was extracted or saved" in body
    assert "Entities" not in body


def test_marker_is_registered():
    assert MARKERS["bible"] == MARKER_BIBLE == "<!-- nano:bible -->"


@pytest.fixture
def wired(fake, monkeypatch, tmp_path):
    monkeypatch.setattr(
        github_cli, "api_factory", lambda: GitHubAPI("test-token", REPO, API, transport=fake)
    )
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    return fake


@pytest.mark.intent("AC-story-bible-31")
def test_cli_keeps_one_comment_per_pull_request(wired, tmp_path):
    path = tmp_path / "bible-diff.json"
    path.write_text(json.dumps(diff()), encoding="utf-8")
    assert main(["github", "bible-report", "--pr", "12", "--diff", str(path)]) == 0
    assert main(["github", "bible-report", "--pr", "12", "--reason", "the AI runner is offline"]) == 0
    bodies = wired.bodies(12)
    assert len(bodies) == 1 and bodies[0].startswith(MARKER_BIBLE)
    assert "did not run" in bodies[0] and "the AI runner is offline" in bodies[0]
    assert "dry run" in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_cli_needs_exactly_one_of_diff_or_reason(wired, tmp_path):
    with pytest.raises(SystemExit):
        main(["github", "bible-report", "--pr", "12"])
    assert main(["github", "bible-report", "--pr", "12", "--diff", str(tmp_path / "none.json")]) == 2
