"""Flat passage list with content hashes (``passages_deduplicated.json``)."""

from __future__ import annotations

import hashlib
from typing import Any

from nanoif.twee.parse import StoryGraph


def content_hash(content: str) -> str:
    """Return the stable hash used to detect unchanged passages.

    Args:
        content: Passage text.

    Returns:
        The first 16 hex digits of the SHA-256 of the UTF-8 text.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def extract_passages(story_graph: StoryGraph) -> dict[str, Any]:
    """Flatten a story graph into the ``passages_deduplicated`` artifact.

    Args:
        story_graph: A parsed story.

    Returns:
        ``{"passages": [{"name", "content", "content_hash"}, ...]}`` sorted by name.
    """
    return {
        "passages": [
            {
                "name": name,
                "content": story_graph["passages"][name]["content"],
                "content_hash": content_hash(story_graph["passages"][name]["content"]),
            }
            for name in sorted(story_graph.get("passages", {}))
        ]
    }
