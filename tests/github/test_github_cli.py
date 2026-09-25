"""``nanoif github`` subcommands against the fake server."""

from __future__ import annotations

import io
import json

import pytest
from github_fakes import API, BOT, HEAD_SHA, REPO, make_editor, make_finding, make_review

import nanoif.github.cli as github_cli
from nanoif.cli import main
from nanoif.github.api import GitHubAPI
from nanoif.github.comments import MARKER_BUILD, MARKER_CONTINUITY, MARKER_STYLE


@pytest.fixture
def wired(fake, monkeypatch, tmp_path):
    fake.pulls[12] = {"number": 12, "head": {"sha": HEAD_SHA}}
    monkeypatch.setattr(
        github_cli, "api_factory", lambda: GitHubAPI("test-token", REPO, API, transport=fake)
    )
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_RUN_ID", "99")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    return fake


def _write_review(tmp_path, review):
    path = tmp_path / "ai-review.json"
    path.write_text(json.dumps(review))
    return path


@pytest.mark.intent("AC-continuity-review-2", "AC-continuity-review-7")
def test_report_upserts_both_comments_and_check_runs_on_the_pr_head(wired, tmp_path):
    review = make_review(make_editor(findings=[make_finding()]), make_editor("style"))
    path = _write_review(tmp_path, review)
    assert main(["github", "report", "--pr", "12", "--review", str(path)]) == 0
    assert main(["github", "report", "--pr", "12", "--review", str(path)]) == 0
    bodies = wired.bodies(12)
    assert len(bodies) == 2
    assert bodies[0].startswith(MARKER_CONTINUITY) and bodies[1].startswith(MARKER_STYLE)
    runs = [(r["name"], r["conclusion"], r["head_sha"]) for r in wired.check_runs]
    assert runs[:2] == [
        ("Continuity Editor", "neutral", HEAD_SHA),
        ("Style Editor", "success", HEAD_SHA),
    ]
    assert "run #99" in (tmp_path / "summary.md").read_text()


@pytest.mark.intent("AC-continuity-review-12")
def test_report_reapplies_dismissals(wired, tmp_path):
    review = make_review(make_editor(findings=[make_finding()]), make_editor("style"))
    path = _write_review(tmp_path, review)
    dismissals = tmp_path / "dismissals.jsonl"
    record = {
        "key": "f-1a2b3c4d",
        "passages": ["Day 1 EV", "Back at the ferry"],
        "hashes": ["h1", "h2"],
        "by": "w",
        "pr": 12,
        "at": "2026-11-03T09:30:00Z",
        "reason": "",
    }
    dismissals.write_text(json.dumps(record) + "\n")
    args = [
        "github",
        "report",
        "--pr",
        "12",
        "--review",
        str(path),
        "--dismissals",
        str(dismissals),
    ]
    assert main(args) == 0
    assert "### Continuity Editor: No findings" in wired.bodies(12)[0]
    assert wired.check_runs[0]["conclusion"] == "success"


def _rerender_args(path, sidecar, head_sha, output):
    return [
        "github",
        "report",
        "--pr",
        "12",
        "--review",
        str(path),
        "--review-head-sha-file",
        str(sidecar),
        "--head-sha",
        head_sha,
        "--github-output",
        str(output),
    ]


@pytest.mark.intent("ADR-022")
def test_rerender_of_a_review_of_the_current_head_posts_on_that_head(wired, tmp_path):
    current = "c" * 40  # differs from the fake PR head, so the explicit sha must be used
    review = make_review(make_editor(findings=[make_finding()]), make_editor("style"))
    path = _write_review(tmp_path, review)
    sidecar = tmp_path / "ai-review-head-sha.txt"
    sidecar.write_text(current + "\n")
    output = tmp_path / "output.txt"
    assert main(_rerender_args(path, sidecar, current, output)) == 0
    assert len(wired.bodies(12)) == 2
    assert [r["head_sha"] for r in wired.check_runs] == [current, current]
    assert "rendered<<" in output.read_text() and "\ntrue\n" in output.read_text()


@pytest.mark.intent("ADR-022")
@pytest.mark.parametrize("recorded", ["d" * 40, "", None])
def test_rerender_of_a_review_of_another_or_unknown_commit_posts_nothing(
    wired, tmp_path, capsys, recorded
):
    wired.add_comment(12, BOT, f"{MARKER_CONTINUITY}\n### Continuity Editor: did not run")
    path = _write_review(tmp_path, make_review(make_editor(findings=[make_finding()])))
    sidecar = tmp_path / "ai-review-head-sha.txt"
    if recorded is not None:
        sidecar.write_text(recorded + "\n")
    output = tmp_path / "output.txt"
    assert main(_rerender_args(path, sidecar, HEAD_SHA, output)) == 0
    assert wired.writes() == []
    assert wired.bodies(12) == [f"{MARKER_CONTINUITY}\n### Continuity Editor: did not run"]
    assert "\nfalse\n" in output.read_text()
    assert "not re-rendered" in capsys.readouterr().out


def test_rerender_check_needs_the_current_head(wired, tmp_path, capsys):
    path = _write_review(tmp_path, make_review())
    sidecar = tmp_path / "ai-review-head-sha.txt"
    sidecar.write_text(HEAD_SHA + "\n")
    args = ["github", "report", "--pr", "12", "--review", str(path)]
    assert main([*args, "--review-head-sha-file", str(sidecar)]) == 2
    assert wired.writes() == []
    assert "--head-sha" in capsys.readouterr().err


def test_report_without_pr_writes_only_the_step_summary(tmp_path, monkeypatch):
    def no_api():
        raise AssertionError("no GitHub call expected")

    monkeypatch.setattr(github_cli, "api_factory", no_api)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    path = _write_review(tmp_path, make_review())
    assert main(["github", "report", "--review", str(path)]) == 0
    text = summary.read_text()
    assert "### Continuity Editor: No findings" in text and "<!-- nano:" not in text


def test_report_with_missing_or_invalid_review_is_a_usage_error(wired, tmp_path, capsys):
    assert main(["github", "report", "--pr", "12", "--review", str(tmp_path / "nope.json")]) == 2
    bad = _write_review(tmp_path, {"version": 1})
    assert main(["github", "report", "--pr", "12", "--review", str(bad)]) == 2
    assert wired.writes() == []
    assert "schema violation" in capsys.readouterr().err


def test_api_failure_exits_1_with_message(wired, tmp_path, capsys):
    wired.fail[("POST", r"/repos/owner/story/issues/\d+/comments")] = 502
    path = _write_review(tmp_path, make_review())
    assert main(["github", "report", "--pr", "12", "--review", str(path)]) == 1
    assert "HTTP 502" in capsys.readouterr().err


@pytest.mark.intent("AC-continuity-review-9")
def test_unavailable_posts_both_editors_as_failures(wired):
    assert main(["github", "unavailable", "--pr", "12", "--reason", "exe runner offline"]) == 0
    assert all("AI review unavailable: exe runner offline" in b for b in wired.bodies(12))
    assert [r["conclusion"] for r in wired.check_runs] == ["failure", "failure"]


@pytest.mark.intent("AC-continuity-review-28")
def test_not_run_replaces_stale_results_and_fails_both_checks_on_the_commit(wired):
    wired.add_comment(12, BOT, f"{MARKER_CONTINUITY}\n### Continuity Editor: No findings")
    wired.add_comment(12, BOT, f"{MARKER_STYLE}\n### Style Editor: 1 finding")
    args = ["github", "not-run", "--pr", "12", "--reason", "the build failed"]
    assert main([*args, "--head-sha", "d" * 40]) == 0
    bodies = wired.bodies(12)
    assert len(bodies) == 2
    assert all("did not run for commit `ddddddd`: the build failed" in b for b in bodies)
    assert not any("No findings" in b or "1 finding" in b for b in bodies)
    runs = [(r["name"], r["conclusion"], r["head_sha"]) for r in wired.check_runs]
    assert runs == [
        ("Continuity Editor", "failure", "d" * 40),
        ("Style Editor", "failure", "d" * 40),
    ]


def test_not_run_requires_the_commit(wired):
    with pytest.raises(SystemExit) as excinfo:
        main(["github", "not-run", "--pr", "12", "--reason", "x"])
    assert excinfo.value.code == 2


def test_unavailable_rejects_unknown_editor(wired):
    with pytest.raises(SystemExit) as excinfo:
        main(["github", "unavailable", "--pr", "12", "--reason", "x", "--editors", "world"])
    assert excinfo.value.code == 2


def test_pending_replaces_stale_comment_without_check_runs(wired):
    stale = wired.add_comment(12, BOT, f"{MARKER_CONTINUITY}\n### Continuity Editor: No findings")
    assert main(["github", "pending", "--pr", "12", "--editors", "continuity"]) == 0
    assert "running" in stale["body"] and "No findings" not in stale["body"]
    assert wired.check_runs == []


@pytest.mark.intent("AC-build-and-deploy-6", "AC-structure-check-20", "AC-structure-check-21")
def test_build_report_posts_comment_and_structure_check(wired, tmp_path):
    structure = tmp_path / "structure.json"
    structure.write_text(
        json.dumps(
            [
                {
                    "level": "error",
                    "code": "broken-link",
                    "file": "src/EV-20261103.twee",
                    "line": 7,
                    "passage": "The weir",
                    "message": "'The weir' links to 'The mill', which does not exist",
                }
            ]
        )
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "play.html").write_text("x")
    args = [
        "github",
        "build-report",
        "--pr",
        "12",
        "--structure",
        str(structure),
        "--dist",
        str(dist),
    ]
    assert main(args) == 0
    assert wired.bodies(12)[0].startswith(MARKER_BUILD)
    run = wired.check_runs[0]
    assert (run["name"], run["conclusion"]) == ("Structure", "failure")
    assert run["output"]["annotations"][0]["path"] == "src/EV-20261103.twee"


@pytest.mark.intent("AC-build-and-deploy-7")
def test_build_report_with_failed_build_and_no_dist(wired, tmp_path):
    structure = tmp_path / "structure.json"
    structure.write_text("[]")
    args = [
        "github",
        "build-report",
        "--pr",
        "12",
        "--structure",
        str(structure),
        "--dist",
        str(tmp_path / "missing"),
        "--build-outcome",
        "failure",
    ]
    assert main(args) == 0
    assert "build failed" in wired.bodies(12)[0]


def _build_report_args(structure, dist, *extra):
    return [
        "github",
        "build-report",
        "--pr",
        "12",
        "--structure",
        str(structure),
        "--dist",
        str(dist),
        *extra,
    ]


@pytest.mark.intent("AC-build-and-deploy-7", "AC-structure-check-18")
def test_build_report_when_an_early_step_failed_replaces_the_stale_comment(wired, tmp_path):
    stale = wired.add_comment(
        12, BOT, f"{MARKER_BUILD}\n### Build & Structure: built, structure clean\n0 errors"
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    args = _build_report_args(
        dist / "structure.json",
        dist,
        "--build-outcome",
        "skipped",
        "--structure-outcome",
        "skipped",
        "--head-sha",
        "d" * 40,
    )
    assert main(args) == 0
    assert wired.bodies(12) == [stale["body"]]
    assert "The build failed before the structure check could run" in stale["body"]
    assert "0 errors" not in stale["body"] and "Preview" not in stale["body"]
    run = wired.check_runs[0]
    assert (run["name"], run["conclusion"], run["head_sha"]) == ("Structure", "failure", "d" * 40)


@pytest.mark.intent("AC-structure-check-18")
def test_build_report_when_the_structure_step_failed_ignores_its_partial_output(wired, tmp_path):
    structure = tmp_path / "structure.json"
    structure.write_text("[]")
    args = _build_report_args(
        structure, tmp_path, "--build-outcome", "skipped", "--structure-outcome", "failure"
    )
    assert main(args) == 0
    body = wired.bodies(12)[0]
    assert "The structure check could not run" in body and "0 errors" not in body
    assert wired.check_runs[0]["conclusion"] == "failure"


@pytest.mark.intent("AC-structure-check-18")
def test_build_report_with_a_missing_structure_file_reports_it_and_exits_2(
    wired, tmp_path, capsys
):
    args = _build_report_args(tmp_path / "absent.json", tmp_path)
    assert main(args) == 2
    assert "The structure check could not run" in wired.bodies(12)[0]
    assert wired.check_runs[0]["conclusion"] == "failure"
    assert "absent.json" in capsys.readouterr().err


@pytest.mark.intent("AC-build-and-deploy-7")
def test_build_report_for_a_failed_build_shows_no_stale_sizes_or_preview(wired, tmp_path):
    structure = tmp_path / "structure.json"
    structure.write_text("[]")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "play.html").write_text("old")
    assert main(_build_report_args(structure, dist, "--build-outcome", "failure")) == 0
    body = wired.bodies(12)[0]
    assert "build failed" in body
    assert "play.html" not in body and "Preview" not in body


def test_build_report_with_unreadable_structure_is_usage_error(wired, tmp_path):
    structure = tmp_path / "structure.json"
    structure.write_text("not json")
    args = [
        "github",
        "build-report",
        "--pr",
        "12",
        "--structure",
        str(structure),
        "--dist",
        str(tmp_path),
    ]
    assert main(args) == 2


@pytest.mark.intent("AC-continuity-review-10")
@pytest.mark.parametrize(
    "role, code", [("admin", 0), ("maintain", 0), ("write", 0), ("triage", 1), ("read", 1)]
)
def test_authorize_requires_write_or_better(wired, role, code):
    wired.permissions["wren-writer"] = {"permission": role, "role_name": role}
    assert main(["github", "authorize", "--user", "wren-writer"]) == code


@pytest.mark.intent("AC-continuity-review-10")
def test_authorize_non_collaborator_is_denied(wired):
    assert main(["github", "authorize", "--user", "stranger"]) == 1


def test_react(wired):
    comment = wired.add_comment(12, BOT, "x")
    assert main(["github", "react", "--comment-id", str(comment["id"])]) == 0
    assert wired.reactions == [(comment["id"], "eyes")]


def _outputs(path):
    values, lines = {}, iter(path.read_text().splitlines())
    for line in lines:
        name, delimiter = line.split("<<", 1)
        values[name] = "\n".join(iter(lambda: next(lines), delimiter))
    return values


def test_parse_command_reads_stdin_and_writes_outputs(tmp_path, monkeypatch):
    out = tmp_path / "output"
    monkeypatch.setattr("sys.stdin", io.StringIO("/check-continuity passage=The weir\n"))
    assert main(["github", "parse-command", "--github-output", str(out)]) == 0
    assert _outputs(out) == {
        "command": "check-continuity",
        "mode": "passage",
        "passage": "The weir",
        "key": "",
        "reason": "",
        "error": "",
    }


def test_parse_command_not_a_command(tmp_path, monkeypatch):
    out = tmp_path / "output"
    monkeypatch.setattr("sys.stdin", io.StringIO("LGTM"))
    assert main(["github", "parse-command", "--github-output", str(out)]) == 0
    assert _outputs(out) == {"command": "none"}


@pytest.mark.intent("AC-continuity-review-12")
def test_dismiss_appends_record_with_hashes(tmp_path):
    review = make_review(make_editor(findings=[make_finding()]), make_editor("style"))
    path = _write_review(tmp_path, review)
    out = tmp_path / "ai" / "dismissals.jsonl"
    args = [
        "github",
        "dismiss",
        "--key",
        "f-1a2b3c4d",
        "--by",
        "wren-writer",
        "--pr",
        "12",
        "--reason",
        "on purpose",
        "--review",
        str(path),
        "--out",
        str(out),
    ]
    assert main(args) == 0
    record = json.loads(out.read_text())
    assert record["hashes"] == ["h1", "h2"] and record["by"] == "wren-writer"


@pytest.mark.intent("AC-continuity-review-12")
def test_dismiss_without_artifact_is_refused_and_writes_nothing(tmp_path, capsys):
    out = tmp_path / "dismissals.jsonl"
    args = [
        "github",
        "dismiss",
        "--key",
        "f-1a2b3c4d",
        "--by",
        "w",
        "--pr",
        "12",
        "--review",
        str(tmp_path / "absent.json"),
        "--out",
        str(out),
    ]
    assert main(args) == 1
    assert not out.exists()
    assert "no AI review result" in capsys.readouterr().err


def test_dismiss_unknown_key_writes_nothing_and_exits_1(tmp_path):
    path = _write_review(tmp_path, make_review())
    out = tmp_path / "dismissals.jsonl"
    args = [
        "github",
        "dismiss",
        "--key",
        "f-00000000",
        "--by",
        "w",
        "--pr",
        "12",
        "--review",
        str(path),
        "--out",
        str(out),
    ]
    assert main(args) == 1
    assert not out.exists()
