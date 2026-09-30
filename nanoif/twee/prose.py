"""Readable prose from passage text, and word counts."""

from __future__ import annotations

import re
from collections.abc import Iterable

from nanoif.twee.links import display_text

MACRO_START_RE = re.compile(r"\([a-z0-9_\-]+:", re.IGNORECASE)
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


def macro_spans(text: str) -> list[tuple[int, int]]:
    """Return the ``[start, end)`` span of every Harlowe macro call, outermost only.

    Parentheses are balanced and string literals (``"..."`` or ``'...'``, with backslash
    escapes) are skipped, so ``(if: $x is "a (b)")`` and a call running over several lines
    are one span each. An unclosed call runs to the end of the text.

    Args:
        text: Raw passage text.

    Returns:
        Spans in document order.
    """
    spans: list[tuple[int, int]] = []
    index = 0
    while (match := MACRO_START_RE.search(text, index)) is not None:
        start, depth, quote, position = match.start(), 0, "", match.start()
        end = len(text)
        while position < len(text):
            char = text[position]
            if quote:
                if char == "\\":
                    position += 1
                elif char == quote:
                    quote = ""
            elif char in "\"'":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    end = position + 1
                    break
            position += 1
        spans.append((start, end))
        index = end
    return spans


def strip_macros(text: str) -> str:
    """Return ``text`` with every Harlowe macro call removed (see :func:`macro_spans`)."""
    pieces, cursor = [], 0
    for start, end in macro_spans(text):
        pieces.append(text[cursor:start])
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def prose_text(text: str) -> str:
    """Return what a reader sees: links as their text, macros and HTML tags removed.

    Args:
        text: Raw passage text.

    Returns:
        The prose.
    """
    return HTML_TAG_RE.sub("", strip_macros(display_text(text)))


def word_count(text: str) -> int:
    """Count the words a reader sees in a passage.

    Args:
        text: Raw passage text.

    Returns:
        Whitespace-separated tokens in :func:`prose_text`.
    """
    return len(prose_text(text).split())
