"""Compute writing metrics and render ``metrics.html``.

Passages come from ``story_graph.json`` (never re-parsed from twee); the
passage-to-file mapping and passage tags come from ``nanoif.twee.files``.
Passages tagged as page furniture or code (see
:data:`nanoif.twee.prose.NON_PROSE_TAGS`, for example the footer) are not
prose and are left out of every count.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any

from nanoif.formats.common import html_environment
from nanoif.schemas.artifacts import load_artifact
from nanoif.twee.files import PassageLocation, passage_locations
from nanoif.twee.parse import StoryGraph
from nanoif.twee.prose import NON_PROSE_TAGS, word_count

BUCKETS: tuple[tuple[int, float, str], ...] = (
    (0, 100, "0-100"),
    (101, 300, "101-300"),
    (301, 500, "301-500"),
    (501, 1000, "501-1000"),
    (1001, float("inf"), "1000+"),
)


@dataclass(frozen=True)
class MetricsConfig:
    """Inputs of a metrics build.

    Attributes:
        src_dir: Story source (for passage files and tags).
        story_graph_path: ``story_graph.json`` from ``nanoif build core``.
        output_dir: Where ``metrics.html`` goes.
        include: Only count files whose names start with one of these.
        exclude: Skip files whose names start with one of these.
        top_n: How many of the longest passages to list.
    """

    src_dir: Path
    story_graph_path: Path
    output_dir: Path
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    top_n: int = 10


@dataclass(frozen=True)
class MetricsResult:
    """What a metrics build produced.

    Attributes:
        metrics: The numbers rendered on the page.
        html_path: The page.
    """

    metrics: dict[str, Any]
    html_path: Path


def statistics(values: Sequence[int]) -> dict[str, float]:
    """Return min, mean, median and max, all zero for no values.

    Args:
        values: Word counts.

    Returns:
        ``{"min", "mean", "median", "max"}``.
    """
    if not values:
        return {"min": 0, "mean": 0.0, "median": 0.0, "max": 0}
    return {"min": min(values), "mean": mean(values), "median": median(values), "max": max(values)}


def distribution(values: Sequence[int]) -> dict[str, int]:
    """Bucket word counts.

    Args:
        values: Word counts.

    Returns:
        Bucket label to how many values fall in it.
    """
    counts = {label: 0 for _, _, label in BUCKETS}
    for value in values:
        for low, high, label in BUCKETS:
            if low <= value <= high:
                counts[label] += 1
                break
    return counts


def _selected(file_name: str | None, include: Sequence[str], exclude: Sequence[str]) -> bool:
    if file_name is None:
        return not include
    if include and not file_name.startswith(tuple(include)):
        return False
    return not file_name.startswith(tuple(exclude)) if exclude else True


def calculate_metrics(
    story_graph: StoryGraph,
    locations: Mapping[str, PassageLocation],
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    top_n: int = 10,
) -> dict[str, Any]:
    """Compute word-count metrics.

    Args:
        story_graph: A parsed story.
        locations: Passage name to where it is declared (file and tags).
        include: Only count files whose names start with one of these.
        exclude: Skip files whose names start with one of these.
        top_n: How many of the longest passages to list.

    Returns:
        Totals, statistics, distributions, the longest passages and per-file counts.
    """
    passages: list[dict[str, Any]] = []
    for name, passage in story_graph["passages"].items():
        location = locations.get(name)
        if location is not None and not NON_PROSE_TAGS.isdisjoint(location.tags):
            continue
        file_name = location.file.name if location is not None else None
        if not _selected(file_name, include, exclude):
            continue
        count = word_count(passage["content"])
        passages.append({"name": name, "file": file_name, "word_count": count})

    files: dict[str, dict[str, Any]] = {}
    for passage in passages:
        if passage["file"] is None:
            continue
        entry = files.setdefault(
            passage["file"], {"name": passage["file"], "word_count": 0, "passage_count": 0}
        )
        entry["word_count"] += passage["word_count"]
        entry["passage_count"] += 1

    passage_counts = [passage["word_count"] for passage in passages]
    file_counts = [entry["word_count"] for entry in files.values()]
    longest = sorted(passages, key=lambda p: (-p["word_count"], p["name"]))[:top_n]
    return {
        "story_name": story_graph["metadata"]["story_title"],
        "total_words": sum(passage_counts),
        "file_count": len(files),
        "passage_count": len(passages),
        "passage_stats": statistics(passage_counts),
        "file_stats": statistics(file_counts),
        "passage_distribution": distribution(passage_counts),
        "file_distribution": distribution(file_counts),
        "top_passages": [{"name": p["name"], "word_count": p["word_count"]} for p in longest],
        "files": sorted(files.values(), key=lambda entry: entry["name"]),
        "filters": {"include": list(include), "exclude": list(exclude)},
    }


def render_html(metrics: Mapping[str, Any]) -> str:
    """Render ``metrics.html``.

    Args:
        metrics: The result of :func:`calculate_metrics`.

    Returns:
        The HTML page.
    """
    return html_environment().get_template("metrics.html.jinja2").render(metrics=metrics)


def build_metrics(config: MetricsConfig) -> MetricsResult:
    """Compute the metrics and write ``metrics.html``.

    Args:
        config: Inputs; see :class:`MetricsConfig`.

    Returns:
        The metrics and the page written.

    Raises:
        BuildError: If the story graph is missing or not valid JSON.
        ArtifactValidationError: If the story graph does not match its schema.
    """
    story_graph = load_artifact(config.story_graph_path, "story_graph")
    metrics = calculate_metrics(
        story_graph,
        passage_locations(config.src_dir),
        include=config.include,
        exclude=config.exclude,
        top_n=config.top_n,
    )
    config.output_dir.mkdir(parents=True, exist_ok=True)
    html_path = config.output_dir / "metrics.html"
    html_path.write_text(render_html(metrics), encoding="utf-8")
    return MetricsResult(metrics=metrics, html_path=html_path)
