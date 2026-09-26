"""The one quote verifier: is a quoted phrase really in a passage?

Used by the Story Bible (every stored fact quotes its passage) and by the editors (every
finding quotes the passages it names). Imports stay one-way: ``twee <- bible <- review``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_QUOTE_CHARS = str.maketrans({'"': "'", "‘": "'", "’": "'", "“": "'", "”": "'"})
"""Every quotation mark and apostrophe folds to ``'``: a model often quotes dialogue with
other marks than the source uses."""
_WRAPPING = "\"'“”‘’"
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize for quote matching: every quote mark to ``'``, whitespace collapsed.

    Args:
        text: Any text.

    Returns:
        The normalized text.
    """
    return _SPACE_RE.sub(" ", text.translate(_QUOTE_CHARS)).strip()


def clean_quote(text: str) -> str:
    """Strip surrounding whitespace and the quotation marks a model wraps a quote in.

    Args:
        text: The quote as the model wrote it.

    Returns:
        The quote itself.
    """
    return text.strip().strip(_WRAPPING).strip()


def quote_found(quote: str, texts: Iterable[str]) -> bool:
    """Return whether a quote is a whitespace-normalized substring of any of ``texts``.

    Args:
        quote: The quote.
        texts: Renderings of the cited passage.

    Returns:
        True when found; an empty quote is never found.
    """
    needle = normalize_text(clean_quote(quote))
    if not needle:
        return False
    return any(needle in normalize_text(text) for text in texts)
