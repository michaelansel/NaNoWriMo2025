"""The Story Bible preview comment and check run on every pull request push (ADR-026)."""

from __future__ import annotations

import json

import pytest
from github_fakes import API, REPO

from nanoif.cli import main
from nanoif.github import cli as github_cli
from nanoif.github.api import GitHubAPI
from nanoif.github.bible import (
    PREVIEW_ARTIFACT,
    PREVIEW_CHECK,
    render_bible_preview,
    render_bible_preview_not_run,
)
from nanoif.github.comments import MARKER_BIBLE
from nanoif.github.report import RunInfo
from nanoif.schemas.artifacts import validate_artifact

RUN = RunInfo(run_id="42", url="https://example.invalid/runs/42")
HEAD = "0123456789abcdef0123456789abcdef01234567"
CAP = "monthly AI spend cap reached: $10.00 of $10.00 in 2026-11 (resets 2026-12-01 UTC)"


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
        "entities": {"added": ["hollis-crane"], "removed": [], "changed": ["pip-halloway"]},
        "facts": {"added": ["hollis-crane#1", "pip-halloway#3"], "reworded": [], "retired": []},
        "conflicts": {"added": [], "retired": []},
        "usage": {"calls": 2, "usd": 0.0042, "usd_known": True, "profile": "exe",
                  "model": "glm"},
        "store": {"status": "used", "hits": ["Hollin Reach"], "misses": 1, "invalid": 0,
                  "write_failed": 0, "reason": ""},
    }
    data.update(overrides)
    validate_artifact(data, "bible_diff")
    return data


@pytest.mark.intent("AC-story-bible-34", "ADR-026")
def test_a_preview_names_the_commit_what_was_read_and_where_to_find_it():
    rendered = render_bible_preview(diff(), RUN, HEAD)
    body = rendered.body
    assert body.startswith(MARKER_BIBLE)
    assert "### Story Bible: preview of this pull request" in body
    assert "0123456" in body and PREVIEW_ARTIFACT in body and "run #42" in body
    assert "*Hollin Reach*" in body and "*The widow's door*" in body
    assert "1 passage" in body and "already read" in body
    assert "from this pull request (not merged)" in body
    assert "may change after merge" in body and "$0.0042" in body
    assert "dry run" not in body
    assert rendered.check.name == PREVIEW_CHECK == "Story Bible preview"
    assert rendered.check.conclusion == "success"


@pytest.mark.intent("ADR-026")
def test_nothing_to_read_succeeds():
    rendered = render_bible_preview(
        diff(status="up_to_date", passages_read=[],
             entities={"added": [], "removed": [], "changed": []},
             facts={"added": [], "reworded": [], "retired": []},
             usage={"calls": 0, "usd": 0.0, "usd_known": True},
             store={"status": "used", "hits": [], "misses": 0, "invalid": 0, "write_failed": 0,
                    "reason": ""}),
        RUN, HEAD,
    )
    assert "### Story Bible: Nothing to read" in rendered.body
    assert rendered.check.conclusion == "success"
    assert rendered.check.title == "Story Bible preview: Nothing to read"


@pytest.mark.intent("AC-story-bible-35", "ADR-026")
def test_a_partial_preview_lists_the_passages_not_read_and_fails():
    rendered = render_bible_preview(
        diff(status="partial", passages_read=["Hollin Reach"],
             passages_failed=[{"passage": "The widow's door",
                               "reason": "LLMTransportError: down (after one re-attempt)"}]),
        RUN, HEAD,
    )
    assert "partial" in rendered.body.splitlines()[1]
    assert "*The widow's door*: LLMTransportError: down" in rendered.body
    assert "as not read" in rendered.body
    assert rendered.check.conclusion == "failure"


@pytest.mark.intent("AC-story-bible-35", "ADR-026")
@pytest.mark.parametrize(
    "reason", ["the exe runner is offline", CAP], ids=["runner", "spend-cap"]
)
def test_did_not_run_says_why_shows_mains_bible_and_fails(reason):
    rendered = render_bible_preview_not_run(reason, RUN, HEAD)
    body = rendered.body
    assert body.startswith(MARKER_BIBLE) and "### Story Bible: did not run" in body
    assert reason in body and "0123456" in body
    assert "`main`" in body and "not read" in body
    assert "Entities" not in body
    assert rendered.check.conclusion == "failure" and rendered.check.name == PREVIEW_CHECK


@pytest.fixture
def wired(fake, monkeypatch, tmp_path):
    monkeypatch.setattr(
        github_cli, "api_factory", lambda: GitHubAPI("test-token", REPO, API, transport=fake)
    )
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    return fake


@pytest.mark.intent("AC-story-bible-33", "ADR-026")
def test_cli_preview_replaces_the_bible_comment_and_checks_the_head(wired, tmp_path):
    path = tmp_path / "bible-diff.json"
    path.write_text(json.dumps(diff()), encoding="utf-8")
    base = ["github", "bible-report", "--preview", "--pr", "12", "--head-sha", HEAD]
    assert main([*base, "--diff", str(path)]) == 0
    assert main([*base, "--reason", "the build failed"]) == 0
    bodies = wired.bodies(12)
    assert len(bodies) == 1 and "did not run" in bodies[0] and "the build failed" in bodies[0]
    runs = [(r["name"], r["conclusion"], r["head_sha"]) for r in wired.check_runs]
    assert runs == [(PREVIEW_CHECK, "success", HEAD), (PREVIEW_CHECK, "failure", HEAD)]
    assert "preview" in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_cli_without_preview_posts_no_check_run(wired, tmp_path):
    assert main(["github", "bible-report", "--pr", "12", "--reason", "offline"]) == 0
    assert wired.check_runs == []
