"""Shared fixtures: a throwaway git repository with a small story."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

STORY_DATA = (
    ':: StoryData\n{"ifid": "ABC-123", "format": "Harlowe", "format-version": "3.3.9", "start": "Start"}\n'
)
STORY_TITLE = ":: StoryTitle\nTest Story\n"
DAY_ONE = (
    ":: Start\nMorning. [[Go left->Left]] or [[Go right->Right]]\n\n"
    ":: Left\nYou went left. [[End1]]\n\n"
    ":: Right\nYou went right. [[End2]]\n"
)
ENDINGS = ":: End1\nLeft ending.\n\n:: End2\nRight ending.\n"


def git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return its stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        env={
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(repo),
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    ).stdout


def commit_all(repo: Path, message: str, date: str) -> str:
    """Stage everything, commit with a fixed author date, return the sha."""
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=test@example.invalid", "commit", "-q", "-m", message, f"--date={date}")
    return git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def story_repo(tmp_path: Path) -> Path:
    """A git repository whose ``src/`` holds a five-passage story committed in two commits."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    (repo / "src" / "StoryData.twee").write_text(STORY_DATA, encoding="utf-8")
    (repo / "src" / "StoryTitle.twee").write_text(STORY_TITLE, encoding="utf-8")
    (repo / "src" / "AB-20251101.twee").write_text(DAY_ONE, encoding="utf-8")
    commit_all(repo, "day one", "2025-11-01T10:00:00+00:00")
    (repo / "src" / "AB-20251102.twee").write_text(ENDINGS, encoding="utf-8")
    commit_all(repo, "endings", "2025-11-02T10:00:00+00:00")
    return repo
