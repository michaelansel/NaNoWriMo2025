"""Shared fixtures for the review tests."""

from __future__ import annotations

import pytest
from review_helpers import EVAL_SRC, load_review_story

from nanoif.review.units import ReviewStory


@pytest.fixture(scope="session")
def eval_story() -> ReviewStory:
    return load_review_story(EVAL_SRC)
