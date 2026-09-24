"""Make model-derived and writer-derived text safe to put in a GitHub comment.

Everything a model wrote (descriptions, quotes) and everything taken from story files
(passage names) passes through :func:`sanitize` before it reaches a template. The
rendered Markdown must not be able to ping people, embed images, carry links, inject
HTML, forge a sticky-comment marker, or break out of the line it sits on.
"""

from __future__ import annotations

import re

ZWJ = "\u200d"  # zero-width joiner: breaks @mentions without changing how they read
DEFAULT_MAX_CHARS = 1000
ELLIPSIS = "…"

_DANGEROUS_SCHEME = re.compile(r"\b(javascript|vbscript|data|file):", re.IGNORECASE)
# Link targets may hold one level of parentheses: (javascript:alert(1)).
_TARGET = r"\((?:[^()\n]|\([^()\n]*\))*\)"
_IMAGE = re.compile(r"!\[([^\]\n]*)\]" + _TARGET)
_LINK = re.compile(r"\[([^\]\n]*)\]" + _TARGET)
_REF_DEFINITION = re.compile(r"^\s*\[[^\]\n]+\]:\s*\S+.*$", re.MULTILINE)
_BARE_URL = re.compile(r"\b(?:https?|ftp)://[^\s`<>]+|\bwww\.[^\s`<>]+", re.IGNORECASE)
_MENTION = re.compile(r"(?<![\w`])@(?=[A-Za-z0-9])")
_WHITESPACE = re.compile(r"\s+")


def _defuse_url(match: re.Match[str]) -> str:
    # Inside a code span GitHub neither autolinks nor renders the URL.
    return f"`{match.group(0)}`"


def sanitize(text: str | None, max_chars: int = DEFAULT_MAX_CHARS, inline: bool = True) -> str:
    """Neutralize Markdown, HTML, links, images and mentions in untrusted text.

    Args:
        text: Model- or writer-derived text; ``None`` becomes ``""``.
        max_chars: Cap on the returned length (an ellipsis marks a cut).
        inline: Collapse all whitespace, including newlines, to single spaces so the
            text cannot open a heading, list, table or code fence.

    Returns:
        Text safe to interpolate into a comment body.
    """
    if not text:
        return ""
    # Blocked schemes first so neither a link target nor a bare URL can execute.
    text = _DANGEROUS_SCHEME.sub(lambda m: f"blocked-{m.group(1).lower()}:", text)
    # Images vanish (alt text kept); links keep their text and lose their target.
    text = _IMAGE.sub(lambda m: m.group(1), text)
    text = _LINK.sub(lambda m: m.group(1), text)
    text = _REF_DEFINITION.sub("", text)
    # Backticks from the model could close our code spans; make them plain quotes.
    text = text.replace("`", "'")
    # HTML: escape everything, which also defeats forged <!-- nano:... --> markers.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Leftover brackets cannot form links or images once escaped.
    text = text.replace("[", "\\[").replace("]", "\\]")
    text = _BARE_URL.sub(_defuse_url, text)
    text = _MENTION.sub(f"@{ZWJ}", text)
    if inline:
        text = _WHITESPACE.sub(" ", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - len(ELLIPSIS)].rstrip() + ELLIPSIS
    return text
