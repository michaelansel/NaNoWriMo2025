"""The formatting bot's commit (ADR-025) and what the Build comment says about it.

Golden files live in ``tests/github/golden/``; a diff there is a change writers see.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from github_fakes import API, HEAD_SHA, REPO

import nanoif.github.cli as github_cli
from nanoif.cli import main
from nanoif.errors import BuildError
from nanoif.github.api import GitHubAPI
from nanoif.github.comments import MARKER_BUILD
from nanoif.github.formatting import FormatCommit, commit_message, parse_format_commit
from nanoif.github.report import (
    FormatNote,
    RunInfo,
    format_line,
    render_build,
    render_format_not_started,
)

GOLDEN = Path(__file__).resolve().parent / "golden"
RUN = RunInfo("4242", "https://github.com/owner/story/actions/runs/4242")
PREVIOUS = "c" * 40
NEW = "d" * 40
SUMMARY = {
    "files": [
        {"file": "src/EV-20261101.twee", "fixed": {"smart-quotes": 2, "trailing-whitespace": 1}},
        {"file": "src/EV-20261102.twee", "fixed": {}},
        {"file": "src/EV-20261103.twee", "fixed": {"final-newline": 1}},
    ],
    "total": 4,
}


@pytest.mark.intent("ADR-025")
def test_commit_message_has_the_subject_and_the_trailer():
    message = commit_message(SUMMARY, PREVIOUS)
    lines = message.splitlines()
    assert lines[0] == "style: fix 4 formatting issues in EV-20261101.twee, EV-20261103.twee"
    assert lines[-1] == f"Nanoif-Format: {PREVIOUS}"
    assert message.endswith("\n")


@pytest.mark.intent("ADR-025")
def test_one_issue_is_singular():
    summary = {"files": [{"file": "src/EV-20261101.twee", "fixed": {"final-newline": 1}}], "total": 1}
    assert commit_message(summary, PREVIOUS).startswith(
        "style: fix 1 formatting issue in EV-20261101.twee\n"
    )


@pytest.mark.intent("ADR-025")
def test_there_is_no_commit_message_for_nothing_fixed():
    with pytest.raises(BuildError, match="nothing was fixed"):
        commit_message({"files": [{"file": "src/EV-20261101.twee", "fixed": {}}], "total": 0}, PREVIOUS)
    with pytest.raises(BuildError, match="full commit sha"):
        commit_message(SUMMARY, "abc123")


@pytest.mark.intent("ADR-025")
def test_the_commit_message_parses_back():
    assert parse_format_commit(commit_message(SUMMARY, PREVIOUS)) == FormatCommit(
        4, ("EV-20261101.twee", "EV-20261103.twee"), PREVIOUS
    )


@pytest.mark.intent("ADR-025")
@pytest.mark.parametrize(
    "message",
    [
        "Add day 3\n",
        "style: fix 4 formatting issues in EV-20261101.twee\n",
        f"style: tidy EV-20261101.twee\n\nNanoif-Format: {PREVIOUS}\n",
        f"style: fix 4 formatting issues in ../../etc/passwd\n\nNanoif-Format: {PREVIOUS}\n",
        "style: fix 4 formatting issues in EV-20261101.twee\n\nNanoif-Format: abc\n",
    ],
)
def test_anything_else_is_not_a_format_commit(message):
    assert parse_format_commit(message) is None


def _fixed_note(sha=NEW):
    return FormatNote("fixed", 4, ("EV-20261101.twee", "EV-20261103.twee"), sha, None)


@pytest.mark.intent("ADR-025")
def test_build_comment_says_what_the_bot_fixed():
    rendered = render_build([], None, RUN, build_ok=True, formatting=_fixed_note())
    assert rendered.body == (GOLDEN / "build_format_fixed.md").read_text(encoding="utf-8")
    assert rendered.check.conclusion == "success"


@pytest.mark.intent("ADR-025")
@pytest.mark.parametrize(
    ("note", "line"),
    [
        (
            FormatNote("refused", 0, (), None, "fixing src/EV-20261101.twee would change its words"),
            "**Formatting could not be fixed automatically:** fixing src/EV-20261101.twee would "
            "change its words. Nothing was changed; the formatting warnings are in "
            "[run #4242](https://github.com/owner/story/actions/runs/4242).",
        ),
        (
            FormatNote("push-failed", 0, (), None, "the branch moved; the newer run formats it"),
            "**Formatting was not applied:** the branch moved; the newer run formats it.",
        ),
        (
            FormatNote("dispatch-failed", 4, ("EV-20261101.twee",), NEW, "HTTP 500"),
            "**Formatting:** the bot fixed 4 issues in `EV-20261101.twee` as `ddddddd`, but the "
            "checks for that commit could not start: HTTP 500; edit any file or ask a "
            "maintainer to re-run.",
        ),
    ],
)
def test_format_lines(note, line):
    assert format_line(note, RUN) == line


@pytest.mark.intent("ADR-025")
def test_a_reason_is_sanitized():
    note = FormatNote("push-failed", 0, (), None, "denied <!-- nano:build --> @owner")
    line = format_line(note, RUN)
    assert "<!--" not in line and "@owner" not in line


@pytest.mark.intent("ADR-025")
def test_checks_not_started_comment_matches_golden():
    note = FormatNote("dispatch-failed", 4, ("EV-20261101.twee", "EV-20261103.twee"), NEW, "HTTP 500")
    body = render_format_not_started(note, RUN)
    assert body == (GOLDEN / "build_format_not_started.md").read_text(encoding="utf-8")


# -- CLI ---------------------------------------------------------------------------------


@pytest.fixture
def wired(fake, monkeypatch, tmp_path):
    fake.pulls[12] = {"number": 12, "head": {"sha": HEAD_SHA}}
    monkeypatch.setattr(
        github_cli, "api_factory", lambda: GitHubAPI("test-token", REPO, API, transport=fake)
    )
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_RUN_ID", "4242")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/story")
    return fake


def _structure_and_dist(tmp_path):
    structure = tmp_path / "structure.json"
    structure.write_text("[]", encoding="utf-8")
    dist = tmp_path / "dist"
    dist.mkdir()
    return ["--structure", str(structure), "--dist", str(dist)]


@pytest.mark.intent("ADR-025")
def test_format_message_writes_the_commit_message(tmp_path):
    summary = tmp_path / "lint-fix.json"
    summary.write_text(json.dumps(SUMMARY), encoding="utf-8")
    out = tmp_path / "message.txt"
    argv = ["github", "format-message", "--summary", str(summary), "--previous-sha", PREVIOUS]
    assert main([*argv, "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == commit_message(SUMMARY, PREVIOUS)


@pytest.mark.intent("ADR-025")
def test_format_message_for_nothing_fixed_is_a_usage_error(tmp_path):
    summary = tmp_path / "lint-fix.json"
    summary.write_text(json.dumps({"files": [], "total": 0}), encoding="utf-8")
    out = tmp_path / "message.txt"
    argv = ["github", "format-message", "--summary", str(summary), "--previous-sha", PREVIOUS]
    assert main([*argv, "--out", str(out)]) == 2
    assert not out.exists()


@pytest.mark.intent("ADR-025")
def test_build_report_on_the_bots_commit_says_what_it_fixed(wired, tmp_path):
    message = tmp_path / "head-commit.txt"
    message.write_text(commit_message(SUMMARY, PREVIOUS), encoding="utf-8")
    argv = ["github", "build-report", "--pr", "12", "--head-sha", NEW, *_structure_and_dist(tmp_path)]
    assert main([*argv, "--format-commit", str(message)]) == 0
    body = wired.bodies(12)[0]
    assert (
        "**Formatting:** the bot fixed 4 issues in `EV-20261101.twee`, `EV-20261103.twee` as "
        "`ddddddd`; your next edit starts from it." in body
    )
    assert wired.check_runs[0]["head_sha"] == NEW


@pytest.mark.intent("ADR-025")
def test_build_report_on_a_writers_commit_says_nothing_about_formatting(wired, tmp_path):
    message = tmp_path / "head-commit.txt"
    message.write_text("Add the weir\n", encoding="utf-8")
    argv = ["github", "build-report", "--pr", "12", "--head-sha", NEW, *_structure_and_dist(tmp_path)]
    assert main([*argv, "--format-commit", str(message)]) == 0
    assert "Formatting" not in wired.bodies(12)[0]


@pytest.mark.intent("ADR-025")
@pytest.mark.parametrize(
    ("problem", "expected"),
    [
        ("refused", "**Formatting could not be fixed automatically:** it would change a word."),
        ("push-failed", "**Formatting was not applied:** it would change a word."),
    ],
)
def test_build_report_says_why_formatting_was_not_applied(wired, tmp_path, problem, expected):
    argv = ["github", "build-report", "--pr", "12", "--head-sha", HEAD_SHA]
    argv += [*_structure_and_dist(tmp_path), "--format-problem", problem]
    assert main([*argv, "--format-reason", "it would change a word"]) == 0
    assert expected in wired.bodies(12)[0]
    assert wired.check_runs[0]["name"] == "Structure"


@pytest.mark.intent("ADR-025")
def test_build_report_when_the_checks_could_not_start_posts_only_the_comment(wired, tmp_path):
    message = tmp_path / "message.txt"
    message.write_text(commit_message(SUMMARY, PREVIOUS), encoding="utf-8")
    argv = ["github", "build-report", "--pr", "12", "--head-sha", NEW, "--format-commit"]
    argv += [str(message), "--format-problem", "dispatch-failed", "--format-reason", "HTTP 500"]
    assert main(argv) == 0
    body = wired.bodies(12)[0]
    assert body.startswith(MARKER_BUILD + "\n### Build & Structure: checks did not start\n")
    assert "could not start: HTTP 500; edit any file" in body
    assert wired.check_runs == []


@pytest.mark.intent("ADR-025")
@pytest.mark.parametrize(
    "extra",
    [
        ["--format-problem", "refused"],
        ["--format-reason", "why"],
        ["--format-problem", "dispatch-failed", "--format-reason", "HTTP 500"],
        ["--format-commit", "{missing}"],
    ],
)
def test_build_report_format_options_that_do_not_fit_are_usage_errors(wired, tmp_path, extra):
    extra = [item.format(missing=tmp_path / "absent.txt") for item in extra]
    argv = ["github", "build-report", "--pr", "12", "--head-sha", NEW, *_structure_and_dist(tmp_path)]
    assert main([*argv, *extra]) == 2
    assert wired.bodies(12) == [] and wired.check_runs == []


def test_build_report_needs_structure_and_dist_unless_the_checks_did_not_start(wired, tmp_path):
    assert main(["github", "build-report", "--pr", "12"]) == 2
