"""Fixtures for Story Bible tests: a committed story repository with the helper passages."""

from __future__ import annotations

from pathlib import Path

import pytest
from bible_helpers import commit, write_story

from nanoif.schemas.artifacts import write_artifact
from nanoif.twee.parse import parse_twee_dir
from tests.conftest import git


@pytest.fixture
def bible_repo(tmp_path: Path) -> Path:
    """A committed repository with src/, lib/artifacts/story_graph.json and no cache."""
    root = tmp_path / "story"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "Test")
    write_story(root)
    write_artifact(root / "lib" / "artifacts" / "story_graph.json", parse_twee_dir(root / "src"),
                   "story_graph")
    git(root, "add", "src")
    git(root, "commit", "-q", "-m", "story")
    return root


@pytest.fixture
def run_repo(tmp_path: Path) -> Path:
    """A committed repository with only src/, for extraction runs."""
    root = tmp_path / "story"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "Test")
    write_story(root)
    commit(root)
    return root
