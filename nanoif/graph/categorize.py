"""Compare the story against a base ref and categorize paths.

The base branch is parsed with the same parser as the working tree
(:func:`nanoif.twee.parse.parse_twee_sources` on raw ``git`` blobs), so a
passage counts as changed only when its text differs, never because two
parsers disagree.

A path's category follows the two-level test from the 2025 design:

1. Did this exact route exist in the base? If so it is ``modified`` when any
   passage on it changed and ``unchanged`` otherwise; it is never ``new``.
2. Otherwise it is ``new`` when it carries new prose (a passage that did not
   exist, or one whose prose changed), and ``modified`` when only links moved
   existing prose onto a new route.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from nanoif.git.service import GitService
from nanoif.graph.paths import enumerate_paths
from nanoif.twee.links import strip_links
from nanoif.twee.parse import StoryGraph, build_graph, parse_twee_sources

Category = Literal["new", "modified", "unchanged"]


@dataclass(frozen=True)
class PassageChange:
    """How one passage in the working tree relates to the base.

    Attributes:
        name: Passage name.
        new: True if the base has no passage of this name.
        changed: True if the text differs from the base (always true when new).
        prose_changed: True if the text differs after links are removed and
            whitespace is collapsed (always true when new).
    """

    name: str
    new: bool
    changed: bool
    prose_changed: bool


@dataclass(frozen=True)
class BaseComparison:
    """The working tree compared with a base commit.

    Attributes:
        base_sha: The commit compared against.
        base_routes: Every route that existed in the base.
        passages: Name to change record, for every passage in the working tree.
        removed: Passages the base had that the working tree does not.
    """

    base_sha: str
    base_routes: frozenset[tuple[str, ...]]
    passages: dict[str, PassageChange]
    removed: list[str]


def normalize_prose(text: str) -> str:
    """Return passage text with links removed and whitespace collapsed.

    Args:
        text: Raw passage text.

    Returns:
        Prose that only changes when the words change.
    """
    return " ".join(strip_links(text).split())


def compare_graphs(head: StoryGraph, base: StoryGraph | None, base_sha: str) -> BaseComparison:
    """Compare a working-tree story graph with a base story graph.

    Args:
        head: The working tree's story, parsed from raw twee.
        base: The base commit's story, or None when the base has no story.
        base_sha: The base commit, recorded in the result.

    Returns:
        Per-passage changes and the set of routes the base had.
    """
    base_passages = base["passages"] if base is not None else {}
    changes: dict[str, PassageChange] = {}
    for name, passage in head["passages"].items():
        if name not in base_passages:
            changes[name] = PassageChange(name, new=True, changed=True, prose_changed=True)
            continue
        old, new = base_passages[name]["content"], passage["content"]
        changes[name] = PassageChange(
            name,
            new=False,
            changed=old != new,
            prose_changed=normalize_prose(old) != normalize_prose(new),
        )
    base_routes: frozenset[tuple[str, ...]] = frozenset()
    if base is not None:
        enumeration = enumerate_paths(build_graph(base), base["start_passage"])
        base_routes = frozenset(tuple(route) for route in enumeration.paths)
    removed = sorted(name for name in base_passages if name not in head["passages"])
    return BaseComparison(base_sha, base_routes, changes, removed)


def categorize_route(route: Sequence[str], comparison: BaseComparison) -> Category:
    """Categorize one path.

    Args:
        route: Passage names in order.
        comparison: The result of :func:`compare_graphs`.

    Returns:
        ``"new"``, ``"modified"`` or ``"unchanged"``.

    Raises:
        KeyError: If a passage on the route is not in the comparison; the
            story graph and the source tree are then out of step.
    """
    changes = [comparison.passages[name] for name in route]
    if tuple(route) in comparison.base_routes:
        return "modified" if any(change.changed for change in changes) else "unchanged"
    return "new" if any(change.prose_changed for change in changes) else "modified"


def load_base_graph(git: GitService, base_ref: str, src_dir: str) -> StoryGraph | None:
    """Parse the story as it was at a base ref, without compiling it.

    Args:
        git: The repository service.
        base_ref: The commit to read the source from.
        src_dir: The source directory relative to the repository root.

    Returns:
        The base story graph, or None when the base has no ``.twee`` files
        under ``src_dir`` (for example a freshly reset repository).

    Raises:
        GitError: If the ref does not resolve.
        StoryParseError: If the base has twee files but no usable story.
    """
    files = git.list_files(base_ref, src_dir, ".twee")
    if not files:
        return None
    return parse_twee_sources(git.read_files(base_ref, files))
