"""Readable prose from passage text, and word counts."""

from __future__ import annotations

import re

from nanoif.twee.links import display_text

HARLOWE_MACRO_RE = re.compile(r"\([a-z\-]+:.*?\)", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")

NON_PROSE_TAGS = frozenset({"script", "stylesheet", "footer", "header", "startup"})
"""Passages with these tags are page furniture or code, not story prose."""


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
