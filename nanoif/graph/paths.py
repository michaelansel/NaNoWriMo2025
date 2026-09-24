"""Path enumeration and path identifiers.

A path is the list of passage names a reader visits from the start passage to
an ending. Enumeration is a depth-first walk that follows links in the order
they appear in each passage, so path numbering is stable across builds.

Two things are never silent:

- a link to a passage that does not exist is reported as a broken link and is
  not followed (the old generator turned it into a fake ending);
- a link back to a passage already on the current path is reported as a cycle
  and is not followed (the old generator dropped the whole branch).

A passage whose links are all broken or cyclic is the end of its path.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from nanoif.errors import GraphError


@dataclass(frozen=True)
class PathEnumeration:
    """The result of walking a story graph.

    Attributes:
        paths: Every path, each a list of passage names, in depth-first order.
        broken_links: ``(source, target)`` pairs where ``target`` is not a passage,
            each once, in the order they were met.
        cycles: Each route that was cut, ending with the passage it would have
            revisited.
    """

    paths: list[list[str]] = field(default_factory=list)
    broken_links: list[tuple[str, str]] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)


def enumerate_paths(graph: Mapping[str, Sequence[str]], start: str) -> PathEnumeration:
    """Walk every path from ``start`` to an ending.

    Args:
        graph: Passage name to the passages it links to, in link order.
        start: The start passage.

    Returns:
        The paths plus the broken links and cycles met on the way.

    Raises:
        GraphError: If ``start`` is not in the graph.
    """
    if start not in graph:
        raise GraphError(f"start passage {start!r} is not in the story graph")
    result = PathEnumeration()
    seen_broken: set[tuple[str, str]] = set()

    def walk(node: str, route: list[str], on_route: set[str]) -> None:
        followable: list[str] = []
        for target in graph[node]:
            if target not in graph:
                if (node, target) not in seen_broken:
                    seen_broken.add((node, target))
                    result.broken_links.append((node, target))
            elif target in on_route:
                result.cycles.append(route + [target])
            else:
                followable.append(target)
        if not followable:
            result.paths.append(route)
            return
        for target in followable:
            walk(target, route + [target], on_route | {target})

    walk(start, [start], {start})
    return result


def path_hash(route: Sequence[str], content: Mapping[str, str]) -> str:
    """Return the 8-character id of a path; it changes when any passage on it changes.

    Args:
        route: Passage names in order.
        content: Passage name to its text.

    Returns:
        The first 8 hex digits of the MD5 of ``name:text`` lines.
    """
    parts = [f"{name}:{content[name]}" if name in content else f"{name}:MISSING" for name in route]
    return hashlib.md5("\n".join(parts).encode("utf-8")).hexdigest()[:8]


def route_hash(route: Sequence[str]) -> str:
    """Return the 8-character id of a route; it depends on passage names only.

    Args:
        route: Passage names in order.

    Returns:
        The first 8 hex digits of the MD5 of the arrow-joined route.
    """
    return hashlib.md5(" → ".join(route).encode("utf-8")).hexdigest()[:8]
