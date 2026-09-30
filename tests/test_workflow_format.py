"""The shape ADR-025 gives ``build-and-deploy.yml``, checked without running it.

A workflow is exercised by a pull request; these tests keep the decisions that a later
edit could silently undo: which jobs may write, which jobs survive a skipped ``format``,
and that pull request jobs take their pull request from ``context``. The file is read as
text, job by job (two-space-indented keys under ``jobs:``), so no YAML library is needed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "build-and-deploy.yml"


def _jobs() -> dict[str, str]:
    text = WORKFLOW.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([a-z][a-z-]*):\n", text, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


JOBS = _jobs()


def _key(block: str, key: str) -> str:
    """The value of a top-level job key, folded (``>-``) lines joined."""
    match = re.search(rf"^    {key}: ?(.*)\n((?:      .*\n)*)", block, flags=re.MULTILINE)
    if match is None:
        return ""
    lines = [match.group(1).strip(), *(line.strip() for line in match.group(2).splitlines())]
    value = " ".join(line for line in lines if line and line != ">-")
    return value.removeprefix("${{").removesuffix("}}").strip()


def _needs(block: str) -> list[str]:
    return re.findall(r"[a-z][a-z-]*", _key(block, "needs"))


@pytest.mark.intent("ADR-025")
def test_the_jobs_are_read():
    assert {"context", "format", "build", "ai-review", "ai-review-not-run"} <= set(JOBS)


@pytest.mark.intent("ADR-025")
def test_only_format_and_bible_extract_may_write_contents():
    writers = sorted(name for name, block in JOBS.items() if "      contents: write" in block)
    assert writers == ["bible-extract", "format"]


@pytest.mark.intent("ADR-025")
def test_format_runs_only_for_same_repository_pull_request_events():
    block = JOBS["format"]
    assert _key(block, "if") == (
        "github.event_name == 'pull_request' && needs.context.outputs.same_repo == 'true'"
    )
    assert _key(block, "timeout-minutes") == "5"
    permissions = re.findall(r"^      ([a-z-]+): (\w+)", block.split("    permissions:\n")[1],
                             flags=re.MULTILINE)
    assert permissions[:3] == [
        ("contents", "write"),
        ("actions", "write"),
        ("pull-requests", "write"),
    ]
    assert "      pushed: " in block and "      new_sha: " in block


@pytest.mark.intent("ADR-025")
def test_build_is_skipped_only_when_format_pushed():
    block = JOBS["build"]
    assert "format" in _needs(block)
    assert _key(block, "if") == "!cancelled() && needs.format.outputs.pushed != 'true'"


@pytest.mark.intent("ADR-025")
@pytest.mark.parametrize(
    "name", [name for name, block in JOBS.items() if "format" in _needs(block)]
)
def test_every_job_that_needs_format_survives_a_skipped_format(name):
    assert _key(JOBS[name], "if").startswith("!cancelled()")


@pytest.mark.intent("ADR-025")
def test_ai_review_not_run_never_speaks_for_a_pushed_over_commit():
    assert "needs.format.outputs.pushed != 'true'" in _key(JOBS["ai-review-not-run"], "if")


@pytest.mark.intent("ADR-025")
def test_pull_request_jobs_read_the_context_not_the_event():
    for name, block in JOBS.items():
        if name != "context":
            assert "github.event.pull_request" not in block, name


@pytest.mark.intent("ADR-025")
def test_the_format_job_starts_intent_before_the_rebuild_that_cancels_it():
    block = JOBS["format"]
    assert block.index("if ! start intent.yml") < block.index("start build-and-deploy.yml")
    assert 'start build-and-deploy.yml -f "pr=$PR_NUMBER"' in block
