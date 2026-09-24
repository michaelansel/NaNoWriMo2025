"""``nanoif build core``: Tweego HTML to the core artifacts every other format consumes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nanoif.errors import BuildError
from nanoif.graph.ids import write_path_id_lookup
from nanoif.schemas.artifacts import write_artifact
from nanoif.twee.parse import parse_story_html
from nanoif.twee.passages import extract_passages


@dataclass(frozen=True)
class CoreBuildResult:
    """What ``build_core`` wrote.

    Attributes:
        story_graph_path: The ``story_graph.json`` artifact.
        passages_path: The ``passages_deduplicated.json`` artifact.
        lookup_path: The generated ``PathIdLookup.twee``.
        passage_count: Passages in the story graph.
        start_passage: Name of the start passage.
        path_count: Routes in the path-id lookup.
    """

    story_graph_path: Path
    passages_path: Path
    lookup_path: Path
    passage_count: int
    start_passage: str
    path_count: int


def build_core(html_path: Path, src_dir: Path, out_dir: Path, lookup_path: Path) -> CoreBuildResult:
    """Parse compiled HTML and write the core artifacts.

    Args:
        html_path: Tweego-compiled HTML (the build uses the paperthin format).
        src_dir: The story source directory; recorded for callers, not read here.
        out_dir: Where ``story_graph.json`` and ``passages_deduplicated.json`` go.
        lookup_path: Where the ``PathIdLookup`` script passage goes.

    Returns:
        Paths and counts.

    Raises:
        BuildError: If ``html_path`` or ``src_dir`` does not exist.
        StoryParseError: If the HTML is not a usable story.
        ArtifactValidationError: If an artifact does not match its schema.
    """
    if not html_path.is_file():
        raise BuildError(f"compiled story not found: {html_path}")
    if not src_dir.is_dir():
        raise BuildError(f"source directory not found: {src_dir}")
    story_graph = parse_story_html(html_path.read_text(encoding="utf-8"))
    story_graph_path = out_dir / "story_graph.json"
    passages_path = out_dir / "passages_deduplicated.json"
    write_artifact(story_graph_path, story_graph, "story_graph")
    write_artifact(passages_path, extract_passages(story_graph), "passages_deduplicated")
    path_count = write_path_id_lookup(story_graph, lookup_path)
    return CoreBuildResult(
        story_graph_path=story_graph_path,
        passages_path=passages_path,
        lookup_path=lookup_path,
        passage_count=len(story_graph["passages"]),
        start_passage=story_graph["start_passage"],
        path_count=path_count,
    )
