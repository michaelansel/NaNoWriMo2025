"""``nanoif build allpaths``: enumerate every path and write the AllPaths outputs.

Outputs under the output directory:

- ``allpaths.html``: a browser page listing every path.
- ``allpaths-clean/path-<id>.txt``: prose only, passage names hidden.
- ``allpaths-metadata/path-<id>.txt``: prose with a header and ``[PASSAGE: id]`` markers.
- ``allpaths-raw/path-<id>.txt``: the same with Twee link markup intact.
- ``allpaths-passage-mapping.json``: passage name to id and back.
- ``allpaths-index.json``: every path's id, route, category, files and dates, and
  every passage's id and whether it changed against the base.
- ``changes.json``: which passages are new or changed against the base.

Categories and dates come from git. There is no validation cache.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from nanoif.errors import BuildError
from nanoif.formats.allpaths.render import path_text, path_text_raw, render_html
from nanoif.git.service import FileDates, GitService
from nanoif.graph.categorize import (
    BaseComparison,
    Category,
    categorize_route,
    compare_graphs,
    load_base_graph,
)
from nanoif.graph.ids import passage_id_mapping
from nanoif.graph.paths import enumerate_paths, path_hash
from nanoif.schemas.artifacts import load_artifact, write_artifact
from nanoif.twee.files import passage_locations, relative_file
from nanoif.twee.parse import StoryGraph, build_graph, parse_twee_dir


@dataclass(frozen=True)
class AllPathsConfig:
    """Inputs of an AllPaths build.

    Attributes:
        repo_root: The git repository root.
        src_dir: The story source directory (inside ``repo_root``).
        story_graph_path: ``story_graph.json`` from ``nanoif build core``.
        output_dir: Where the outputs go (normally ``dist/``).
        base_ref: The git ref to categorize against; see :func:`resolve_base_ref`.
        generated_at: Timestamp for the browser page; defaults to now.
    """

    repo_root: Path
    src_dir: Path
    story_graph_path: Path
    output_dir: Path
    base_ref: str = "HEAD"
    generated_at: datetime | None = None


@dataclass(frozen=True)
class PathRecord:
    """One path, computed once and used by every output.

    Attributes:
        number: 1-based position in enumeration order.
        id: The 8-character path id (route and content).
        route: Passage names in order.
        passage_ids: The passages' ids, aligned with ``route``.
        category: ``new``, ``modified`` or ``unchanged`` against the base.
        files: Source files the path's passages live in, in first-use order.
        created: When the newest of those files was first committed, or None.
        modified: When any of those files was last committed, or None.
    """

    number: int
    id: str
    route: tuple[str, ...]
    passage_ids: tuple[str, ...]
    category: Category
    files: tuple[str, ...]
    created: str | None
    modified: str | None


@dataclass(frozen=True)
class AllPathsResult:
    """What an AllPaths build produced.

    Attributes:
        paths: Every path, in enumeration order.
        base_sha: The commit paths were categorized against.
        counts: Number of paths per category.
        broken_links: ``(source, target)`` links to passages that do not exist.
        cycles: Routes cut because they revisited a passage.
        comparison: The per-passage comparison with the base.
        html_path: The browser page.
    """

    paths: list[PathRecord]
    base_sha: str
    counts: dict[str, int]
    broken_links: list[tuple[str, str]]
    cycles: list[list[str]]
    comparison: BaseComparison
    html_path: Path


def resolve_base_ref(env: Mapping[str, str]) -> str:
    """Pick the ref to categorize against from the workflow environment.

    Args:
        env: Environment variables (normally ``os.environ``).

    Returns:
        ``GITHUB_MERGE_BASE`` when set (a pull request build), else ``HEAD``
        (a local build, which then reports uncommitted changes).

    Raises:
        BuildError: If ``GITHUB_BASE_REF`` is set but ``GITHUB_MERGE_BASE`` is
            not: the workflow must compute the merge base, or every path would
            be categorized against the wrong commit.
    """
    merge_base = env.get("GITHUB_MERGE_BASE", "").strip()
    if merge_base:
        return merge_base
    if env.get("GITHUB_BASE_REF", "").strip():
        raise BuildError(
            "GITHUB_BASE_REF is set but GITHUB_MERGE_BASE is not; the workflow must run "
            "`git merge-base HEAD origin/$GITHUB_BASE_REF` and export it"
        )
    return "HEAD"


def _latest(dates: list[str]) -> str | None:
    if not dates:
        return None
    return max(dates, key=lambda value: datetime.fromisoformat(value))


def _build_records(
    story_graph: StoryGraph,
    routes: list[list[str]],
    comparison: BaseComparison,
    passage_files: Mapping[str, str],
    file_dates: Mapping[str, FileDates],
) -> list[PathRecord]:
    content = {name: passage["content"] for name, passage in story_graph["passages"].items()}
    ids = passage_id_mapping(content)
    records: list[PathRecord] = []
    for number, route in enumerate(routes, start=1):
        files: list[str] = []
        for name in route:
            file = passage_files.get(name)
            if file is not None and file not in files:
                files.append(file)
        dated = [file_dates[file] for file in files if file in file_dates]
        records.append(
            PathRecord(
                number=number,
                id=path_hash(route, content),
                route=tuple(route),
                passage_ids=tuple(ids[name] for name in route),
                category=categorize_route(route, comparison),
                files=tuple(files),
                created=_latest([dates.created for dates in dated]),
                modified=_latest([dates.modified for dates in dated]),
            )
        )
    return records


def _write_path_files(
    output_dir: Path, records: list[PathRecord], content: Mapping[str, str]
) -> None:
    total = len(records)
    renderers = {
        "allpaths-clean": lambda record: path_text(record, content, total, False),
        "allpaths-metadata": lambda record: path_text(record, content, total, True),
        "allpaths-raw": lambda record: path_text_raw(record, content, total),
    }
    for subdir, render in renderers.items():
        directory = output_dir / subdir
        directory.mkdir(parents=True, exist_ok=True)
        for stale in directory.glob("path-*.txt"):
            stale.unlink()
        for record in records:
            (directory / f"path-{record.id}.txt").write_text(render(record), encoding="utf-8")


def _index_document(
    config: AllPathsConfig,
    story_graph: StoryGraph,
    records: list[PathRecord],
    comparison: BaseComparison,
    passage_files: Mapping[str, str],
    enumeration_broken: list[tuple[str, str]],
    enumeration_cycles: list[list[str]],
) -> dict[str, Any]:
    ids = passage_id_mapping(story_graph["passages"])
    return {
        "base_ref": config.base_ref,
        "base_sha": comparison.base_sha,
        "story_title": story_graph["metadata"]["story_title"],
        "paths": [
            {
                "id": record.id,
                "route": list(record.route),
                "passage_ids": list(record.passage_ids),
                "category": record.category,
                "files": list(record.files),
                "created": record.created,
                "modified": record.modified,
            }
            for record in records
        ],
        "passages": [
            {
                "name": name,
                "id": ids[name],
                "file": passage_files.get(name),
                "changed_vs_base": comparison.passages[name].changed,
                "new_vs_base": comparison.passages[name].new,
            }
            for name in sorted(story_graph["passages"])
        ],
        "broken_links": [{"from": source, "to": target} for source, target in enumeration_broken],
        "cycles": [list(cycle) for cycle in enumeration_cycles],
    }


def run(config: AllPathsConfig) -> AllPathsResult:
    """Build every AllPaths output.

    Args:
        config: Inputs; see :class:`AllPathsConfig`.

    Returns:
        The paths and what was found on the way.

    Raises:
        BuildError: If the story graph is missing or does not match the source tree.
        GitError: If ``config.base_ref`` does not resolve.
        StoryParseError: If the source tree or the base cannot be parsed.
        ArtifactValidationError: If an output does not match its schema.
    """
    repo_root = config.repo_root.resolve()
    src_dir = config.src_dir.resolve()
    try:
        src_rel = src_dir.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise BuildError(f"{src_dir} is not inside the repository {repo_root}") from exc

    story_graph = load_artifact(config.story_graph_path, "story_graph")
    enumeration = enumerate_paths(build_graph(story_graph), story_graph["start_passage"])

    head = parse_twee_dir(src_dir)
    missing = sorted(name for name in story_graph["passages"] if name not in head["passages"])
    if missing:
        raise BuildError(
            f"story graph and {src_rel}/ disagree; passages not in source: {missing[:5]}"
            " (rerun `nanoif build core`)"
        )

    git = GitService(repo_root)
    base_sha = git.rev_parse(config.base_ref)
    comparison = compare_graphs(head, load_base_graph(git, config.base_ref, src_rel), base_sha)
    file_dates = git.file_dates(src_rel)
    passage_files = {
        name: relative_file(location, repo_root)
        for name, location in passage_locations(src_dir).items()
        if name in story_graph["passages"]
    }

    records = _build_records(story_graph, enumeration.paths, comparison, passage_files, file_dates)
    content = {name: passage["content"] for name, passage in story_graph["passages"].items()}

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    ids = passage_id_mapping(story_graph["passages"])
    (output_dir / "allpaths-passage-mapping.json").write_text(
        json.dumps({"name_to_id": ids, "id_to_name": {v: k for k, v in ids.items()}}, indent=2),
        encoding="utf-8",
    )
    _write_path_files(output_dir, records, content)
    html_path = output_dir / "allpaths.html"
    html_path.write_text(
        render_html(
            story_graph["metadata"]["story_title"],
            records,
            story_graph["passages"],
            config.generated_at or datetime.now(),
        ),
        encoding="utf-8",
    )
    write_artifact(
        output_dir / "allpaths-index.json",
        _index_document(
            config,
            story_graph,
            records,
            comparison,
            passage_files,
            enumeration.broken_links,
            enumeration.cycles,
        ),
        "allpaths_index",
    )
    write_artifact(
        output_dir / "changes.json",
        {
            "base_ref": config.base_ref,
            "base_sha": base_sha,
            "changed": sorted(
                name for name, change in comparison.passages.items() if change.changed
            ),
            "new": sorted(name for name, change in comparison.passages.items() if change.new),
            "removed": list(comparison.removed),
        },
        "changes",
    )

    counts = {category: 0 for category in ("new", "modified", "unchanged")}
    for record in records:
        counts[record.category] += 1
    return AllPathsResult(
        paths=records,
        base_sha=base_sha,
        counts=counts,
        broken_links=list(enumeration.broken_links),
        cycles=[list(cycle) for cycle in enumeration.cycles],
        comparison=comparison,
        html_path=html_path,
    )

