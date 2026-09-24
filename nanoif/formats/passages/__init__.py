"""Passage index page (``passages.html``): every passage with its file, links and size."""

from nanoif.formats.passages.generator import (
    PassageRow,
    PassagesResult,
    build_passages,
    passage_rows,
)

__all__ = ["PassageRow", "PassagesResult", "build_passages", "passage_rows"]
