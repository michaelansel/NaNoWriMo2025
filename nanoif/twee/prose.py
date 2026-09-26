"""Readable prose from passage text, and word counts."""

from __future__ import annotations

import re
from collections.abc import Iterable

from nanoif.twee.links import display_text

HARLOWE_MACRO_RE = re.compile(r"\([a-z\-]+:.*?\)", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")

NON_PROSE_TAGS = frozenset({"script", "stylesheet", "footer", "header", "startup"})
"""Passages with these tags are page furniture or code, not story prose."""

INFRA_PASSAGES = frozenset(
    {"StoryData", "StoryTitle", "StoryStyles", "PathIdDisplay", "PathIdLookup"}
)
"""Passages that describe or decorate the story rather than tell it."""


def is_infra(name: str, tags: Iterable[str] = ()) -> bool:
    """Return whether a passage is infrastructure rather than story prose.

    The editors and the Story Bible use this one definition, so they read the same
    passages.

    Args:
        name: Passage name.
        tags: Its tags.

    Returns:
        True for the known infrastructure passages and any passage with a code or page tag.
    """
    return name in INFRA_PASSAGES or not NON_PROSE_TAGS.isdisjoint(tags)


def prose_text(text: str) -> str:
    """Return what a reader sees: links as their text, macros and HTML tags removed.

    Args:
        text: Raw passage text.

    Returns:
        The prose.
    """
    return HTML_TAG_RE.sub("", HARLOWE_MACRO_RE.sub("", display_text(text)))


def word_count(text: str) -> int:
    """Count the words a reader sees in a passage.

    Args:
        text: Raw passage text.

    Returns:
        Whitespace-separated tokens in :func:`prose_text`.
    """
    return len(prose_text(text).split())
