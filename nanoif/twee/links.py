"""The one link parser.

Every place that needs to know where a passage links to, or how a link reads as
prose, goes through this module. Supported forms:

- ``[[Target]]``
- ``[[Text->Target]]`` (the rightmost ``->`` separates, so text may contain ``->``)
- ``[[Target<-Text]]`` (the leftmost ``<-`` separates)
- ``[[Text|Target]]`` (Twine 1 style; the rightmost ``|`` separates)
- ``]`` inside the text, as long as it is not ``]]``
- Harlowe macros ``(link-goto: "Text", "Target")``, ``(link-reveal-goto: ...)``,
  ``(click-goto: ...)`` and ``(goto: "Target")``; a single argument is both text and target.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_STRING = r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''

LINK_RE = re.compile(
    r"\[\[(?P<inner>(?:[^\]]|\](?!\]))+?)\]\]"
    r"|\((?P<macro>link-goto|link-reveal-goto|click-goto|goto)\s*:\s*"
    rf"(?P<arg1>{_STRING})(?:\s*,\s*(?P<arg2>{_STRING}))?\s*\)",
    re.IGNORECASE,
)
"""Matches one link in either bracket or macro form."""

UNSELECTED = "[unselected]"
"""Placeholder left where a link the reader did not take used to be."""


@dataclass(frozen=True)
class Link:
    """One link found in passage text.

    Attributes:
        text: What the reader sees.
        target: The passage the link leads to.
        start: Offset of the first character of the link markup.
        end: Offset one past the last character of the link markup.
    """

    text: str
    target: str
    start: int
    end: int


def split_link(inner: str) -> tuple[str, str]:
    """Split the inside of a ``[[...]]`` link into display text and target.

    Args:
        inner: The text between ``[[`` and ``]]``.

    Returns:
        ``(text, target)``, both stripped of surrounding whitespace.
    """
    if "->" in inner:
        cut = inner.rfind("->")
        text, target = inner[:cut], inner[cut + 2 :]
    elif "<-" in inner:
        cut = inner.find("<-")
        target, text = inner[:cut], inner[cut + 2 :]
    elif "|" in inner:
        cut = inner.rfind("|")
        text, target = inner[:cut], inner[cut + 1 :]
    else:
        text = target = inner
    return text.strip(), target.strip()


def _unquote(literal: str) -> str:
    quote = literal[0]
    body = literal[1:-1]
    return body.replace("\\" + quote, quote).replace("\\\\", "\\")


def find_links(text: str) -> list[Link]:
    """Return every link in ``text`` in document order.

    Args:
        text: Raw passage text.

    Returns:
        Links with their display text, target and character span.
    """
    links: list[Link] = []
    for match in LINK_RE.finditer(text):
        if match.group("inner") is not None:
            display, target = split_link(match.group("inner"))
        else:
            first = _unquote(match.group("arg1"))
            second = match.group("arg2")
            target = _unquote(second) if second is not None else first
            display = first if match.group("macro").lower() != "goto" else ""
        links.append(Link(display, target, match.start(), match.end()))
    return links


def link_targets(text: str) -> list[str]:
    """Return the unique link targets in ``text`` in order of first appearance.

    Args:
        text: Raw passage text.

    Returns:
        Passage names, each once, in the order they first appear.
    """
    seen: set[str] = set()
    targets: list[str] = []
    for link in find_links(text):
        if link.target not in seen:
            seen.add(link.target)
            targets.append(link.target)
    return targets


def _replace_links(text: str, replacement: "callable") -> str:  # type: ignore[valid-type]
    pieces: list[str] = []
    cursor = 0
    for link in find_links(text):
        pieces.append(text[cursor : link.start])
        pieces.append(replacement(link))
        cursor = link.end
    pieces.append(text[cursor:])
    return "".join(pieces)


def strip_links(text: str) -> str:
    """Remove all link markup from ``text``, leaving only the surrounding prose.

    Args:
        text: Raw passage text.

    Returns:
        The text with every link (markup and display text) removed.
    """
    return _replace_links(text, lambda _link: "")


def display_text(text: str, selected_target: str | None = None) -> str:
    """Render links as prose, optionally showing only the link that was taken.

    With no ``selected_target`` every link becomes its display text. With one,
    the link to that target becomes its display text and every other link
    becomes :data:`UNSELECTED` when the passage has more than one link, or is
    removed when it is the only link.

    Args:
        text: Raw passage text.
        selected_target: The passage the reader went to next, if known.

    Returns:
        Prose with link markup resolved.
    """
    links = find_links(text)
    placeholder = UNSELECTED if len(links) > 1 else ""

    def render(link: Link) -> str:
        if selected_target is None or link.target == selected_target:
            return link.text
        return placeholder

    return _replace_links(text, render)
