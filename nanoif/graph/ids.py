"""Passage identifiers and the runtime path-id lookup.

Passage ids hide passage names such as ``Day 5 AB`` from the AI reviewers, who
would otherwise read a timeline into them. They are the first 12 hex digits of
the MD5 of the name, so the same passage keeps the same id across builds and a
mapping file can translate them back.

The path-id lookup is a Harlowe ``[script]`` passage that maps every route to
its path id so the playable story can show the id at an ending.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from nanoif.graph.paths import enumerate_paths, path_hash
from nanoif.twee.parse import StoryGraph, build_graph

ROUTE_SEPARATOR = "→"
"""Joins passage names in a lookup key; the runtime JavaScript uses the same character."""

_HELPER_JS = Path(__file__).resolve().parents[1] / "templates" / "js" / "path-id-lookup.js"


def passage_id_mapping(names: Iterable[str]) -> dict[str, str]:
    """Map passage names to stable 12-character hex ids.

    Args:
        names: Passage names.

    Returns:
        Name to id, in sorted name order.
    """
    return {name: hashlib.md5(name.encode("utf-8")).hexdigest()[:12] for name in sorted(names)}


def path_id_lookup(
    paths: Iterable[Sequence[str]], content: Mapping[str, str]
) -> dict[str, str]:
    """Map every route to its path id.

    Args:
        paths: Routes, each a sequence of passage names.
        content: Passage name to its text.

    Returns:
        ``"A→B→C"`` to the 8-character path id.
    """
    return {ROUTE_SEPARATOR.join(route): path_hash(route, content) for route in paths}


def javascript_lookup(lookup: Mapping[str, str]) -> str:
    """Render a lookup as the JavaScript statement that defines ``window.pathIdLookup``.

    Args:
        lookup: Route key to path id.

    Returns:
        One JavaScript statement.
    """
    return f"window.pathIdLookup = {json.dumps(dict(lookup), ensure_ascii=False, indent=2)};"


def render_path_id_lookup(story_graph: StoryGraph) -> tuple[str, int]:
    """Render the ``PathIdLookup`` script passage for a story.

    Args:
        story_graph: A parsed story.

    Returns:
        The Twee text of the passage and the number of routes it knows.
    """
    enumeration = enumerate_paths(build_graph(story_graph), story_graph["start_passage"])
    content = {name: passage["content"] for name, passage in story_graph["passages"].items()}
    lookup = path_id_lookup(enumeration.paths, content)
    helper = _HELPER_JS.read_text(encoding="utf-8")
    twee = f":: PathIdLookup [script]\n{javascript_lookup(lookup)}\n\n{helper}\n"
    return twee, len(lookup)


def write_path_id_lookup(story_graph: StoryGraph, out_path: Path) -> int:
    """Write the ``PathIdLookup`` passage next to the story source.

    Args:
        story_graph: A parsed story.
        out_path: Where to write, normally ``src/PathIdLookup.twee``.

    Returns:
        The number of routes in the lookup.
    """
    twee, count = render_path_id_lookup(story_graph)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(twee, encoding="utf-8")
    return count
