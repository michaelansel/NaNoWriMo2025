"""Sticky pull-request comments: one per check type, found by an HTML marker.

A sticky comment is the bot's comment whose body starts with the marker. It is edited
in place on every run so a pull request carries exactly one Build, one Continuity and
one Style comment. Footer text is never used to find a comment, and a user's comment
that happens to contain the marker is never touched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nanoif.github.api import BOT_LOGIN, GitHubAPI

MARKER_BUILD = "<!-- nano:build -->"
MARKER_CONTINUITY = "<!-- nano:continuity -->"
MARKER_STYLE = "<!-- nano:style -->"
MARKER_BIBLE = "<!-- nano:bible -->"

MARKERS = {
    "build": MARKER_BUILD,
    "continuity": MARKER_CONTINUITY,
    "style": MARKER_STYLE,
    "bible": MARKER_BIBLE,
}


@dataclass(frozen=True)
class UpsertResult:
    """What :func:`upsert_sticky` did."""

    action: str
    comment_id: int
    url: str


def find_sticky(
    comments: list[dict[str, Any]], marker: str, bot_login: str = BOT_LOGIN
) -> dict[str, Any] | None:
    """Return the first bot comment whose body starts with ``marker``.

    Args:
        comments: Issue comments as the API returns them.
        marker: The HTML marker, for example ``<!-- nano:continuity -->``.
        bot_login: The login that owns sticky comments.

    Returns:
        The comment, or ``None``.
    """
    for comment in comments:
        login = (comment.get("user") or {}).get("login")
        body = comment.get("body") or ""
        if login == bot_login and body.lstrip().startswith(marker):
            return comment
    return None


def with_marker(marker: str, body: str) -> str:
    """Return ``body`` with ``marker`` as its first line (added once)."""
    return body if body.startswith(marker) else f"{marker}\n{body}"


def upsert_sticky(
    api: GitHubAPI, pr: int, marker: str, body: str, bot_login: str = BOT_LOGIN
) -> UpsertResult:
    """Edit the pull request's sticky comment for ``marker``, or create it.

    Args:
        api: The GitHub client.
        pr: Pull request number.
        marker: The HTML marker identifying the check type.
        body: The rendered comment; the marker is prepended if missing.
        bot_login: The login that owns sticky comments.

    Returns:
        Whether the comment was ``created``, ``updated`` or left ``unchanged``, with its id.

    Raises:
        GitHubError: If listing, creating or editing fails.
    """
    body = with_marker(marker, body)
    existing = find_sticky(api.list_issue_comments(pr), marker, bot_login)
    if existing is None:
        created = api.create_comment(pr, body)
        return UpsertResult("created", created["id"], created.get("html_url", ""))
    if existing.get("body") == body:
        return UpsertResult("unchanged", existing["id"], existing.get("html_url", ""))
    updated = api.update_comment(existing["id"], body)
    return UpsertResult("updated", updated["id"], updated.get("html_url", ""))
