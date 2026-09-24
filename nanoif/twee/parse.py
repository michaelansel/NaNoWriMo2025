"""The one story parser.

Two inputs produce the same ``story_graph`` structure (see
``nanoif/schemas/artifacts/story_graph.schema.json``):

- Tweego-compiled HTML (any story format; the build uses paperthin), via
  :func:`parse_story_html`.
- Raw Twee source, via :func:`parse_twee_sources` or :func:`parse_twee_dir`.
  This is how a base branch is parsed from ``git`` blobs without compiling it.

The structure is::

    {
        "passages": {"Name": {"content": "...", "links": ["Other", ...]}, ...},
        "start_passage": "Name",
        "metadata": {"story_title": ..., "ifid": ..., "format": ..., "format_version": ...},
    }
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from nanoif.errors import StoryParseError
from nanoif.twee.files import find_twee_files, split_twee
from nanoif.twee.links import link_targets

StoryGraph = dict[str, Any]

SPECIAL_PASSAGES = frozenset({"StoryTitle", "StoryData"})
"""Passages that describe the story rather than belong to it."""

NON_PASSAGE_TAGS = frozenset({"script", "stylesheet"})
"""Tags Tweego compiles into ``<script>``/``<style>`` elements instead of passages."""


class _TweegoHTMLParser(HTMLParser):
    """Collect ``tw-storydata`` attributes and ``tw-passagedata`` elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.story_attrs: dict[str, str] | None = None
        self.passages: dict[str, dict[str, Any]] = {}
        self._current: dict[str, Any] | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "tw-storydata":
            self.story_attrs = attributes
        elif tag == "tw-passagedata":
            self._current = {
                "pid": attributes.get("pid", ""),
                "name": attributes.get("name", ""),
                "tags": attributes.get("tags", "").split(),
            }
            self._chunks = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "tw-passagedata" and self._current is not None:
            self._current["text"] = "".join(self._chunks).strip()
            self.passages[self._current["name"]] = self._current
            self._current = None
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._chunks.append(data)


def _story_graph(
    passages: Mapping[str, str], start_passage: str, metadata: Mapping[str, str]
) -> StoryGraph:
    if not passages:
        raise StoryParseError("story has no passages")
    if start_passage not in passages:
        raise StoryParseError(f"start passage {start_passage!r} is not in the story")
    return {
        "passages": {
            name: {"content": text, "links": link_targets(text)}
            for name, text in passages.items()
            if name not in SPECIAL_PASSAGES
        },
        "start_passage": start_passage,
        "metadata": dict(metadata),
    }


def parse_story_html(html: str) -> StoryGraph:
    """Parse Tweego-compiled HTML into a story graph.

    Args:
        html: The compiled story, as written by ``tweego``.

    Returns:
        The story graph.

    Raises:
        StoryParseError: If the HTML has no ``tw-storydata`` element, no
            passages, or a ``startnode`` that names no passage.
    """
    parser = _TweegoHTMLParser()
    parser.feed(html)
    parser.close()
    if parser.story_attrs is None:
        raise StoryParseError("no <tw-storydata> element: not a Tweego-compiled story")
    attrs = parser.story_attrs
    if not parser.passages:
        raise StoryParseError("story has no passages")
    start_pid = attrs.get("startnode", "")
    start_name = next(
        (name for name, passage in parser.passages.items() if passage["pid"] == start_pid),
        None,
    )
    if start_name is None:
        raise StoryParseError(f"startnode {start_pid!r} names no passage")
    metadata = {
        "story_title": attrs.get("name", "Untitled"),
        "ifid": attrs.get("ifid", ""),
        "format": attrs.get("format", "Unknown"),
        "format_version": attrs.get("format-version", "Unknown"),
    }
    return _story_graph(
        {name: passage["text"] for name, passage in parser.passages.items()},
        start_name,
        metadata,
    )


def parse_twee_sources(sources: Mapping[str, str]) -> StoryGraph:
    """Parse raw Twee source files into a story graph.

    The start passage comes from ``StoryData``'s ``start`` field, or, when that
    is absent, from the Twee 3 default of a passage named ``Start``. Passages
    tagged ``script`` or ``stylesheet`` are skipped, as Tweego does not emit
    them as passages either.

    Args:
        sources: File name to file contents. Files are read in the order
            given; a passage declared twice keeps the first.

    Returns:
        The story graph.

    Raises:
        StoryParseError: If ``StoryData`` is not valid JSON, if there are no
            passages, or if the start passage does not exist.
    """
    passages: dict[str, str] = {}
    for text in sources.values():
        for passage in split_twee(text):
            if NON_PASSAGE_TAGS.isdisjoint(passage.tags):
                passages.setdefault(passage.name, passage.text)
    story_data: dict[str, Any] = {}
    if "StoryData" in passages:
        try:
            story_data = json.loads(passages["StoryData"])
        except json.JSONDecodeError as exc:
            raise StoryParseError(f"StoryData is not valid JSON: {exc}") from exc
    metadata = {
        "story_title": passages.get("StoryTitle", "Untitled").strip() or "Untitled",
        "ifid": str(story_data.get("ifid", "")),
        "format": str(story_data.get("format", "Unknown")),
        "format_version": str(story_data.get("format-version", "Unknown")),
    }
    return _story_graph(passages, str(story_data.get("start", "Start")), metadata)


def parse_twee_dir(src_dir: Path) -> StoryGraph:
    """Parse every ``.twee`` file under a directory into a story graph.

    Args:
        src_dir: Directory holding the story source.

    Returns:
        The story graph.

    Raises:
        StoryParseError: See :func:`parse_twee_sources`.
    """
    return parse_twee_sources(
        {path.as_posix(): path.read_text(encoding="utf-8") for path in find_twee_files(src_dir)}
    )


def build_graph(story_graph: StoryGraph) -> dict[str, list[str]]:
    """Return the adjacency list of a story graph.

    Args:
        story_graph: A parsed story.

    Returns:
        Passage name to the list of passage names it links to, in link order.
    """
    return {name: list(passage["links"]) for name, passage in story_graph["passages"].items()}
