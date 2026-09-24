"""Sticky comments are found by marker on the bot's own comments, never by footer text."""

from __future__ import annotations

from github_fakes import API, BOT, REPO, USER, FakeGitHub

from nanoif.github.api import GitHubAPI
from nanoif.github.comments import (
    MARKER_BUILD,
    MARKER_CONTINUITY,
    MARKER_STYLE,
    find_sticky,
    upsert_sticky,
)


def test_first_upsert_creates_then_second_edits_in_place(api, fake):
    first = upsert_sticky(api, 5, MARKER_CONTINUITY, "### Continuity Editor: 1 finding")
    second = upsert_sticky(api, 5, MARKER_CONTINUITY, "### Continuity Editor: No findings")
    assert first.action == "created" and second.action == "updated"
    assert first.comment_id == second.comment_id
    assert fake.bodies(5) == [f"{MARKER_CONTINUITY}\n### Continuity Editor: No findings"]


def test_identical_body_is_left_unchanged(api, fake):
    upsert_sticky(api, 5, MARKER_BUILD, "same")
    result = upsert_sticky(api, 5, MARKER_BUILD, "same")
    assert result.action == "unchanged"
    assert [r.method for r in fake.writes()] == ["POST"]


def test_each_marker_gets_its_own_comment(api, fake):
    for marker in (MARKER_BUILD, MARKER_CONTINUITY, MARKER_STYLE):
        upsert_sticky(api, 5, marker, "body")
    upsert_sticky(api, 5, MARKER_STYLE, "new style body")
    assert fake.bodies(5) == [
        f"{MARKER_BUILD}\nbody",
        f"{MARKER_CONTINUITY}\nbody",
        f"{MARKER_STYLE}\nnew style body",
    ]


def test_a_user_comment_containing_the_marker_is_never_edited(api, fake):
    user_comment = fake.add_comment(5, USER, f"{MARKER_CONTINUITY}\nI pasted the bot's comment")
    result = upsert_sticky(api, 5, MARKER_CONTINUITY, "bot body")
    assert result.action == "created"
    assert user_comment["body"] == f"{MARKER_CONTINUITY}\nI pasted the bot's comment"
    assert len(fake.bodies(5)) == 2


def test_a_bot_comment_that_only_mentions_the_marker_later_is_not_sticky(api, fake):
    fake.add_comment(5, BOT, f"Recorded dismissal. Footer mentions {MARKER_CONTINUITY} here.")
    fake.add_comment(5, BOT, "Reply `/check-continuity` to re-run")  # footer text only
    result = upsert_sticky(api, 5, MARKER_CONTINUITY, "bot body")
    assert result.action == "created"


def test_sticky_on_a_later_page_is_found():
    fake = FakeGitHub(page_size=3)
    for index in range(7):
        fake.add_comment(9, USER, f"chatter {index}")
    sticky = fake.add_comment(9, BOT, f"{MARKER_BUILD}\nold build")
    api = GitHubAPI("test-token", REPO, api_url=API, transport=fake)
    result = upsert_sticky(api, 9, MARKER_BUILD, "new build")
    assert result.action == "updated" and result.comment_id == sticky["id"]
    assert sticky["body"] == f"{MARKER_BUILD}\nnew build"


def test_find_sticky_ignores_other_bots():
    comments = [{"id": 1, "user": {"login": "other[bot]"}, "body": f"{MARKER_BUILD}\nx"}]
    assert find_sticky(comments, MARKER_BUILD) is None
