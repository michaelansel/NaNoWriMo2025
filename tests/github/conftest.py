"""Fixtures for the GitHub integration tests: a fake server and a client wired to it."""

from __future__ import annotations

import pytest
from github_fakes import API, REPO, FakeGitHub

from nanoif.github.api import GitHubAPI


@pytest.fixture
def fake() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def api(fake: FakeGitHub) -> GitHubAPI:
    return GitHubAPI("test-token", REPO, api_url=API, transport=fake)
