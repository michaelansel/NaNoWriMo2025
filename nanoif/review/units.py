"""Review units: what each editor reads for one passage under review.

A continuity unit for a passage P is P plus the passages a reader may have read before
it (its ancestors in the story graph), in topological order. An ancestor that does not
dominate P (some route to P skips it) is marked ``◇ branch-dependent``. Passage names are
replaced by :func:`nanoif.graph.ids.passage_id_mapping` ids so the model cannot read a
timeline into names such as ``Day 5 AB``.

When the whole ancestor set is over the token budget, the unit is split into routes: the
routes from the start passage to P are enumerated (bounded) and a greedy cover picks at
most :data:`MAX_ROUTES` of them, one unit each. A route still over budget keeps only its
last :data:`TRUNCATE_KEEP` passages before P, with a truncation note. A unit still over
budget after that is marked ``over_budget`` and the runner reports it as skipped.

Infrastructure passages (``StoryData``, ``StoryTitle``, ``StoryStyles``, ``PathIdDisplay``,
the generated lookup, and anything tagged script, stylesheet, footer, header or startup)
are never units and never appear in a unit's context.
"""

from __future__ import annotations

import json
import os
from collections import deque
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from nanoif.build.paths import ProjectPaths
from nanoif.errors import ReviewConfigError
from nanoif.graph.ids import passage_id_mapping
from nanoif.schemas.artifacts import load_artifact
from nanoif.twee.files import PassageLocation, find_twee_files, passage_locations, split_twee
from nanoif.twee.links import display_text
from nanoif.twee.parse import StoryGraph
from nanoif.twee.passages import content_hash
from nanoif.twee.prose import NON_PROSE_TAGS, is_infra

UNIT_BUDGET_ENV = "NANOIF_REVIEW_UNIT_BUDGET"
DEFAULT_UNIT_BUDGET = 20_000
MAX_ROUTES = 4
TRUNCATE_KEEP = 12
ROUTE_ENUMERATION_LIMIT = 2_000
"""Routes to P enumerated before the greedy cover gives up looking for more."""

INFRA_TAGS = NON_PROSE_TAGS
STORY_STYLE_KEYS = ("perspective", "tense", "protagonist")

BRANCH_MARK = "◇ branch-dependent"
PASSAGE_HEADER = "[PASSAGE: {id}]"
BRANCH_HEADER = "[PASSAGE: {id} " + BRANCH_MARK + "]"
REVIEW_HEADER = "[PASSAGE UNDER REVIEW: {id}]"
TRUNCATION_NOTE = "[TRUNCATED: {omitted} earlier passage(s) on this route omitted for length]"

Mode = Literal["changed", "all", "passage"]
UnitKind = Literal["full", "route", "truncated", "single"]
MODES: tuple[str, ...] = ("changed", "all", "passage")


def unit_budget(env: Mapping[str, str] | None = None) -> int:
    """Return the per-unit token budget from ``NANOIF_REVIEW_UNIT_BUDGET``.

    Args:
        env: Mapping to read; defaults to ``os.environ``.

    Returns:
        The budget in estimated tokens.

    Raises:
        ReviewConfigError: The variable is set but is not a positive integer.
    """
    env = os.environ if env is None else env
    raw = env.get(UNIT_BUDGET_ENV, "").strip()
    if not raw:
        return DEFAULT_UNIT_BUDGET
    try:
        value = int(raw)
    except ValueError:
        raise ReviewConfigError(f"{UNIT_BUDGET_ENV} {raw!r} is not an integer") from None
    if value < 1:
        raise ReviewConfigError(f"{UNIT_BUDGET_ENV} must be at least 1, got {value}")
    return value


def estimate_tokens(text: str) -> int:
    """Estimate tokens as characters divided by four.

    Args:
        text: Any text.

    Returns:
        The estimate.
    """
    return len(text) // 4


@dataclass(frozen=True)
class StoryStyleConfig:
    """``storyStyle`` from StoryData, or why it is unusable.

    Attributes:
        values: The usable settings among perspective, tense and protagonist.
        problem: Why the Style Editor cannot run, or ``None`` when it can.
    """

    values: dict[str, str]
    problem: str | None


def read_story_style(src_dir: Path) -> StoryStyleConfig:
    """Read ``storyStyle`` from the ``StoryData`` passage under ``src_dir``.

    Args:
        src_dir: The story source directory.

    Returns:
        The usable settings, with ``problem`` set when there are none.
    """
    for path in find_twee_files(src_dir):
        for passage in split_twee(path.read_text(encoding="utf-8")):
            if passage.name != "StoryData":
                continue
            try:
                data = json.loads(passage.text)
            except json.JSONDecodeError as exc:
                return StoryStyleConfig({}, f"StoryData is not valid JSON ({exc.msg})")
            style = data.get("storyStyle") if isinstance(data, dict) else None
            if not isinstance(style, dict):
                return StoryStyleConfig(
                    {}, "StoryData has no storyStyle (perspective, tense, protagonist)"
                )
            values = {
                key: style[key].strip()
                for key in STORY_STYLE_KEYS
                if isinstance(style.get(key), str) and style[key].strip()
            }
            if not values:
                return StoryStyleConfig(
                    {}, "storyStyle sets none of perspective, tense, protagonist"
                )
            return StoryStyleConfig(values, None)
    return StoryStyleConfig({}, "no StoryData passage in the story source")


@dataclass(frozen=True)
class ReviewStory:
    """The story as the editors see it: prose passages only.

    Attributes:
        start: The start passage.
        content: Passage name to raw text, for every non-infrastructure passage.
        graph: Passage name to the passages it links to (existing, non-infrastructure).
        ids: Passage name to its stable id.
        locations: Passage name to where it is declared, when known.
        style: The ``storyStyle`` settings.
        repo: The repository root, for repository-relative file names.
    """

    start: str
    content: dict[str, str]
    graph: dict[str, list[str]]
    ids: dict[str, str]
    locations: dict[str, PassageLocation] = field(default_factory=dict)
    style: StoryStyleConfig = field(default_factory=lambda: StoryStyleConfig({}, "not read"))
    repo: Path | None = None

    @classmethod
    def from_graph(
        cls,
        story_graph: StoryGraph,
        tags: Mapping[str, Sequence[str]] | None = None,
        locations: Mapping[str, PassageLocation] | None = None,
        style: StoryStyleConfig | None = None,
        repo: Path | None = None,
    ) -> ReviewStory:
        """Build from a ``story_graph`` artifact, dropping infrastructure passages.

        Args:
            story_graph: The parsed story (``lib/artifacts/story_graph.json``).
            tags: Passage name to its tags, from the source files.
            locations: Passage name to its declaration site.
            style: The ``storyStyle`` settings.
            repo: The repository root.

        Returns:
            The review view of the story.

        Raises:
            ReviewConfigError: The start passage is missing or is infrastructure.
        """
        tags = tags or {}
        content = {
            name: passage["content"]
            for name, passage in story_graph["passages"].items()
            if not is_infra(name, tags.get(name, ()))
        }
        start = story_graph["start_passage"]
        if start not in content:
            raise ReviewConfigError(f"start passage {start!r} is not a prose passage")
        graph = {
            name: [
                target
                for target in story_graph["passages"][name]["links"]
                if target in content
            ]
            for name in content
        }
        return cls(
            start=start,
            content=content,
            graph=graph,
            ids=passage_id_mapping(content),
            locations=dict(locations or {}),
            style=style or StoryStyleConfig({}, "not read"),
            repo=repo,
        )

    def name_for_id(self) -> dict[str, str]:
        """Return the id-to-name mapping."""
        return {passage_id: name for name, passage_id in self.ids.items()}

    def hash(self, name: str) -> str:
        """Return the content hash of a passage.

        Args:
            name: A passage in the story.

        Returns:
            :func:`nanoif.twee.passages.content_hash` of its text.
        """
        return content_hash(self.content[name])


def load_story(paths: ProjectPaths) -> ReviewStory:
    """Load the built story graph and the source-side facts the editors need.

    Args:
        paths: The repository layout.

    Returns:
        The review view of the story.

    Raises:
        BuildError: ``story_graph.json`` is missing or unreadable (run ``nanoif build``).
        ArtifactValidationError: It does not match its schema.
        ReviewConfigError: The start passage is unusable.
    """
    story_graph = load_artifact(paths.story_graph, "story_graph")
    locations = passage_locations(paths.src) if paths.src.is_dir() else {}
    tags = {name: location.tags for name, location in locations.items()}
    style = (
        read_story_style(paths.src)
        if paths.src.is_dir()
        else StoryStyleConfig({}, f"story source {paths.src} not found")
    )
    return ReviewStory.from_graph(story_graph, tags, locations, style, paths.repo)


def select_passages(
    story: ReviewStory,
    mode: str,
    changes: Mapping[str, Any] | None = None,
    passage: str | None = None,
) -> list[str]:
    """Pick the passages to review.

    Args:
        story: The story.
        mode: ``changed`` (passages in ``changes["changed"]``), ``all`` (every prose
            passage), or ``passage`` (the one named).
        changes: The ``changes.json`` artifact; required for ``changed``.
        passage: The passage name; required for ``passage``.

    Returns:
        Passage names, sorted (``changed``, ``all``) or the one named.

    Raises:
        ReviewConfigError: Unknown mode, missing input for the mode, or a passage that is
            not a prose passage of the story.
    """
    if mode == "changed":
        if changes is None:
            raise ReviewConfigError("mode 'changed' needs dist/changes.json (run nanoif build)")
        return sorted(name for name in changes["changed"] if name in story.content)
    if mode == "all":
        return sorted(story.content)
    if mode == "passage":
        if not passage:
            raise ReviewConfigError("mode 'passage' needs --passage NAME")
        if passage not in story.content:
            raise ReviewConfigError(
                f"passage {passage!r} is not a prose passage of this story"
            )
        return [passage]
    raise ReviewConfigError(f"unknown review mode {mode!r}; expected one of {MODES}")


# -- graph analysis -------------------------------------------------------------------


def preorder(graph: Mapping[str, Sequence[str]], start: str) -> list[str]:
    """Return passages reachable from ``start`` in depth-first preorder (link order).

    Args:
        graph: Adjacency.
        start: The start passage.

    Returns:
        Reachable passages, each once.
    """
    order: list[str] = []
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        order.append(node)
        stack.extend(reversed([t for t in graph.get(node, ()) if t not in seen]))
    return order


def dominators(graph: Mapping[str, Sequence[str]], start: str) -> dict[str, frozenset[str]]:
    """Compute the dominator set of every passage reachable from ``start``.

    A passage D dominates P when every route from the start passage to P passes
    through D. Iterative data-flow over reachable passages; no route enumeration.

    Args:
        graph: Adjacency.
        start: The start passage.

    Returns:
        Reachable passage to its dominators (itself included).
    """
    order = preorder(graph, start)
    reachable = set(order)
    preds: dict[str, list[str]] = {node: [] for node in order}
    for node in order:
        for target in graph.get(node, ()):
            if target in reachable:
                preds[target].append(node)
    everything = frozenset(order)
    dom: dict[str, frozenset[str]] = {node: everything for node in order}
    dom[start] = frozenset({start})
    changed = True
    while changed:
        changed = False
        for node in order[1:]:
            incoming = [dom[p] for p in preds[node]]
            new = frozenset.intersection(*incoming) | {node} if incoming else frozenset({node})
            if new != dom[node]:
                dom[node] = new
                changed = True
    return dom


def ancestors(graph: Mapping[str, Sequence[str]], target: str) -> set[str]:
    """Return every passage with a route to ``target`` (``target`` excluded).

    Args:
        graph: Adjacency.
        target: The passage.

    Returns:
        The ancestor set.
    """
    preds: dict[str, list[str]] = {}
    for node, targets in graph.items():
        for linked in targets:
            preds.setdefault(linked, []).append(node)
    found: set[str] = set()
    queue = deque([target])
    while queue:
        node = queue.popleft()
        for pred in preds.get(node, ()):
            if pred not in found:
                found.add(pred)
                queue.append(pred)
    found.discard(target)
    return found


def topological_order(
    graph: Mapping[str, Sequence[str]], nodes: Collection[str], rank: Mapping[str, int]
) -> list[str]:
    """Order ``nodes`` so links point forward, breaking cycles and ties by ``rank``.

    Args:
        graph: Adjacency.
        nodes: The passages to order.
        rank: Tie-break order (depth-first preorder); unranked passages sort last by name.

    Returns:
        The passages in reading order.
    """
    members = set(nodes)
    indegree = {node: 0 for node in members}
    for node in members:
        for target in graph.get(node, ()):
            if target in members and target != node:
                indegree[target] += 1

    def key(node: str) -> tuple[int, str]:
        return (rank.get(node, len(rank)), node)

    remaining = set(members)
    order: list[str] = []
    while remaining:
        ready = [node for node in remaining if indegree[node] == 0]
        node = min(ready or remaining, key=key)
        remaining.discard(node)
        order.append(node)
        for target in graph.get(node, ()):
            if target in remaining and target != node:
                indegree[target] -= 1
    return order


def routes_to(
    graph: Mapping[str, Sequence[str]],
    start: str,
    target: str,
    allowed: Collection[str],
    limit: int = ROUTE_ENUMERATION_LIMIT,
) -> list[list[str]]:
    """Enumerate simple routes from ``start`` to ``target`` through ``allowed`` passages.

    Args:
        graph: Adjacency.
        start: The start passage.
        target: The passage the routes end at.
        allowed: Passages a route may pass through (the target's ancestors).
        limit: Stop after this many routes.

    Returns:
        Routes in depth-first link order, each ending at ``target``.
    """
    if start == target:
        return [[target]]
    routes: list[list[str]] = []
    stack: list[tuple[str, list[str]]] = [(start, [start])]
    while stack and len(routes) < limit:
        node, route = stack.pop()
        branches: list[tuple[str, list[str]]] = []
        for linked in graph.get(node, ()):
            if linked == target:
                routes.append(route + [target])
                if len(routes) >= limit:
                    break
            elif linked in allowed and linked not in route:
                branches.append((linked, route + [linked]))
        stack.extend(reversed(branches))
    return routes


def greedy_route_cover(
    routes: Sequence[Sequence[str]], wanted: Collection[str], limit: int = MAX_ROUTES
) -> list[list[str]]:
    """Pick at most ``limit`` routes that together cover as many ``wanted`` passages as possible.

    Args:
        routes: Candidate routes.
        wanted: Passages to cover (the ancestors).
        limit: Maximum routes picked.

    Returns:
        The chosen routes, in the order picked.
    """
    covered: set[str] = set()
    chosen: list[list[str]] = []
    remaining = set(wanted)
    while len(chosen) < limit and remaining:
        best: Sequence[str] | None = None
        best_gain = 0
        for route in routes:
            gain = len(remaining.intersection(route))
            if gain > best_gain:
                best, best_gain = route, gain
        if best is None:
            break
        chosen.append(list(best))
        covered.update(best)
        remaining -= covered
    return chosen


# -- units ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnitPassage:
    """One passage as it appears inside a unit.

    Attributes:
        name: Passage name (never shown to the model).
        id: Passage id shown in the header.
        text: The passage as rendered in the unit (links resolved).
        branch_dependent: True when some route to the passage under review skips it.
        under_review: True for the passage under review.
    """

    name: str
    id: str
    text: str
    branch_dependent: bool
    under_review: bool


@dataclass(frozen=True)
class ReviewUnit:
    """One model call's worth of story text.

    Attributes:
        editor: ``continuity`` or ``style``.
        passage: Name of the passage under review.
        passages: Context passages in reading order, then the passage under review.
        text: The rendered story text sent to the model.
        tokens: Estimated tokens of ``text``.
        budget: The budget ``tokens`` is measured against.
        kind: ``full`` (every ancestor), ``route``, ``truncated``, or ``single`` (style).
        route_index: 1-based route number for route and truncated units, else ``None``.
        route_count: Routes the passage was split into, else ``None``.
        omitted: Earlier passages dropped by truncation.
    """

    editor: str
    passage: str
    passages: tuple[UnitPassage, ...]
    text: str
    tokens: int
    budget: int
    kind: UnitKind
    route_index: int | None = None
    route_count: int | None = None
    omitted: int = 0

    @property
    def over_budget(self) -> bool:
        """Whether the unit is still larger than its budget."""
        return self.tokens > self.budget

    @property
    def under_review(self) -> UnitPassage:
        """The passage under review."""
        return self.passages[-1]

    @property
    def by_id(self) -> dict[str, UnitPassage]:
        """Unit passages keyed by id."""
        return {entry.id: entry for entry in self.passages}

    @property
    def tag(self) -> str:
        """Log and fixture tag, for example ``continuity:The toll#2``."""
        suffix = f"#{self.route_index}" if self.route_index is not None else ""
        return f"{self.editor}:{self.passage}{suffix}"

    @property
    def note(self) -> str | None:
        """What a reader of the report should know about this unit's coverage."""
        parts: list[str] = []
        if self.route_index is not None and self.route_count is not None:
            parts.append(f"route {self.route_index} of {self.route_count}")
        if self.omitted:
            parts.append(f"{self.omitted} earlier passage(s) omitted for length")
        return "; ".join(parts) or None


def render_unit_text(passages: Sequence[UnitPassage], omitted: int = 0) -> str:
    """Render unit passages in the text form the prompts consume.

    Args:
        passages: Context passages then the passage under review.
        omitted: Earlier passages dropped by truncation (adds a note first).

    Returns:
        The story text with ``[PASSAGE: id]`` headers.
    """
    blocks: list[str] = []
    if omitted:
        blocks.append(TRUNCATION_NOTE.format(omitted=omitted))
    for entry in passages:
        if entry.under_review:
            header = REVIEW_HEADER
        elif entry.branch_dependent:
            header = BRANCH_HEADER
        else:
            header = PASSAGE_HEADER
        blocks.append(f"{header.format(id=entry.id)}\n{entry.text}")
    return "\n\n".join(blocks) + "\n"


def _make_unit(
    story: ReviewStory,
    editor: str,
    target: str,
    context: Sequence[str],
    branch_dependent: Collection[str],
    selected: Mapping[str, Collection[str]],
    budget: int,
    kind: UnitKind,
    route_index: int | None = None,
    route_count: int | None = None,
    omitted: int = 0,
) -> ReviewUnit:
    entries = [
        UnitPassage(
            name=name,
            id=story.ids[name],
            text=display_text(story.content[name], selected[name]),
            branch_dependent=name in branch_dependent,
            under_review=False,
        )
        for name in context
    ]
    entries.append(
        UnitPassage(
            name=target,
            id=story.ids[target],
            text=display_text(story.content[target]),
            branch_dependent=False,
            under_review=True,
        )
    )
    text = render_unit_text(entries, omitted)
    return ReviewUnit(
        editor=editor,
        passage=target,
        passages=tuple(entries),
        text=text,
        tokens=estimate_tokens(text),
        budget=budget,
        kind=kind,
        route_index=route_index,
        route_count=route_count,
        omitted=omitted,
    )


def continuity_units(
    story: ReviewStory, target: str, budget: int = DEFAULT_UNIT_BUDGET
) -> list[ReviewUnit]:
    """Build the continuity units for one passage under review.

    Args:
        story: The story.
        target: The passage under review.
        budget: Token budget per unit.

    Returns:
        One unit when everything fits; otherwise one unit per covering route (at most
        :data:`MAX_ROUTES`), each truncated to its last :data:`TRUNCATE_KEEP` passages when
        needed. A returned unit may still be ``over_budget``.

    Raises:
        ReviewConfigError: ``target`` is not a prose passage.
    """
    if target not in story.content:
        raise ReviewConfigError(f"passage {target!r} is not a prose passage of this story")
    rank = {name: index for index, name in enumerate(preorder(story.graph, story.start))}
    reachable = target in rank
    found = ancestors(story.graph, target)
    if reachable:
        found = {name for name in found if name in rank}
        doms = dominators(story.graph, story.start)[target]
        branch = {name for name in found if name not in doms}
    else:
        branch = set(found)
    order = topological_order(story.graph, found, rank)
    members = set(order) | {target}
    union_selected = {name: members for name in order}

    full = _make_unit(story, "continuity", target, order, branch, union_selected, budget, "full")
    if not full.over_budget:
        return [full]

    routes = (
        greedy_route_cover(routes_to(story.graph, story.start, target, found), found)
        if reachable
        else []
    )
    if not routes:
        if len(order) <= TRUNCATE_KEEP:
            return [full]
        return [_truncated(story, target, order, branch, union_selected, budget, None, None)]
    units: list[ReviewUnit] = []
    for index, route in enumerate(routes, start=1):
        context = route[:-1]
        selected = {name: {route[i + 1]} for i, name in enumerate(context)}
        unit = _make_unit(
            story, "continuity", target, context, branch, selected, budget, "route",
            route_index=index, route_count=len(routes),
        )
        if unit.over_budget and len(context) > TRUNCATE_KEEP:
            unit = _truncated(story, target, context, branch, selected, budget, index, len(routes))
        units.append(unit)
    return units


def _truncated(
    story: ReviewStory,
    target: str,
    context: Sequence[str],
    branch: Collection[str],
    selected: Mapping[str, Collection[str]],
    budget: int,
    route_index: int | None,
    route_count: int | None,
) -> ReviewUnit:
    kept = list(context[-TRUNCATE_KEEP:])
    return _make_unit(
        story, "continuity", target, kept, branch, selected, budget, "truncated",
        route_index=route_index, route_count=route_count, omitted=len(context) - len(kept),
    )


def style_unit(story: ReviewStory, target: str, budget: int = DEFAULT_UNIT_BUDGET) -> ReviewUnit:
    """Build the single-passage Style Editor unit.

    Args:
        story: The story.
        target: The passage under review.
        budget: Token budget per unit.

    Returns:
        A unit holding only the passage under review.

    Raises:
        ReviewConfigError: ``target`` is not a prose passage.
    """
    if target not in story.content:
        raise ReviewConfigError(f"passage {target!r} is not a prose passage of this story")
    return _make_unit(story, "style", target, [], (), {}, budget, "single")
