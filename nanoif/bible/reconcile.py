"""Stage 3, reconcile: duplicate groups and conflicts among one entity's facts (ADR-020).

Only entities touched in the run (or still pending from an earlier one) are sent, in
batches of at most :data:`MAX_INPUT_TOKENS` estimated input tokens per call, each entity as
``{slug, name, aliases, facts[{id, claim, passage}]}``. The answer names fact ids only.
Code checks, per entity, that every id exists and belongs to that entity, that no id is in
two duplicate groups, and that no conflict pairs a fact with itself or two duplicates. An
entity whose answer fails a check, is missing, or whose call failed after one re-attempt
gets an ``error`` and stays ``pending``; the others are applied.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nanoif.bible.cache import Entity
from nanoif.llm.client import Completer
from nanoif.llm.errors import LLMError, LLMRunHalted
from nanoif.llm.prompts import prompt_schema, render_prompt

PROMPT = "bible_reconcile"
REASONING_EFFORT = "medium"
MAX_INPUT_TOKENS = 8_000


@dataclass(frozen=True)
class ReconcileResult:
    """What reconciliation decided for one entity.

    Attributes:
        duplicates: Groups of fact ids that state the same fact (each of size 2 or more).
        conflicts: ``(a, b, note)`` pairs of fact ids that cannot both be true.
        error: Why the entity stays pending, or ``None`` when the result is usable.
    """

    duplicates: tuple[tuple[str, ...], ...] = ()
    conflicts: tuple[tuple[str, str, str], ...] = ()
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Whether the result passed every check and can be applied."""
        return self.error is None


def reconcile_tag(batch: int) -> str:
    """Return the completer tag of the ``batch``-th reconcile call (from 1)."""
    return f"bible-reconcile:{batch}"


def _payload(entity: Entity) -> dict[str, Any]:
    return {
        "slug": entity.slug,
        "name": entity.name,
        "aliases": list(entity.aliases),
        "facts": [{"id": f.id, "claim": f.claim, "passage": f.passage} for f in entity.facts],
    }


def _tokens(text: str) -> int:
    return len(text) // 4 + 1


def _batches(entities: Sequence[Entity]) -> list[list[Entity]]:
    overhead = render_prompt(PROMPT, entities=[])
    budget = MAX_INPUT_TOKENS - _tokens(overhead.system) - _tokens(overhead.user)
    batches: list[list[Entity]] = []
    current: list[Entity] = []
    used = 0
    for entity in entities:
        size = _tokens(render_prompt(PROMPT, entities=[_payload(entity)]).user) - _tokens(
            overhead.user
        )
        if current and used + size > budget:
            batches.append(current)
            current, used = [], 0
        current.append(entity)
        used += size
    if current:
        batches.append(current)
    return batches


def check_answer(entity: Entity, answer: Mapping[str, Any] | None) -> ReconcileResult:
    """Check one entity's part of a ``bible_reconcile`` answer.

    Args:
        entity: The entity as it was sent.
        answer: Its ``{slug, duplicates, conflicts}`` entry, or ``None`` when missing.

    Returns:
        The usable result, or one with ``error`` set.
    """
    if answer is None:
        return ReconcileResult(error=f"{entity.slug} is missing from the answer")
    own = {fact.id for fact in entity.facts}
    group_of: dict[str, int] = {}
    groups: list[tuple[str, ...]] = []
    for raw in answer["duplicates"]:
        group = tuple(dict.fromkeys(raw))
        for fid in group:
            if fid not in own:
                return ReconcileResult(error=f"{fid} is not a fact of {entity.slug}")
        if len(group) < 2:
            continue
        for fid in group:
            if fid in group_of:
                return ReconcileResult(error=f"{fid} is in two duplicate groups")
            group_of[fid] = len(groups)
        groups.append(group)
    conflicts: list[tuple[str, str, str]] = []
    for raw in answer["conflicts"]:
        a, b = raw["a"], raw["b"]
        for fid in (a, b):
            if fid not in own:
                return ReconcileResult(error=f"{fid} is not a fact of {entity.slug}")
        if a == b:
            return ReconcileResult(error=f"conflict pairs {a} with itself")
        if a in group_of and group_of.get(a) == group_of.get(b):
            return ReconcileResult(error=f"conflict {a}/{b} pairs two duplicates")
        conflicts.append((a, b, raw["note"].strip()))
    return ReconcileResult(tuple(groups), tuple(conflicts))


def reconcile(client: Completer, entities: Sequence[Entity]) -> dict[str, ReconcileResult]:
    """Reconcile the facts of each entity.

    Entities with fewer than two facts need no call and get an empty result.

    Args:
        client: The completer.
        entities: The entities to reconcile (live facts only are sent).

    Returns:
        Slug to result, for every entity given.

    Raises:
        LLMRunHalted: The client will make no more calls; the run must stop.
    """
    results = {entity.slug: ReconcileResult() for entity in entities if len(entity.facts) < 2}
    todo = [entity for entity in entities if len(entity.facts) >= 2]
    for number, batch in enumerate(_batches(todo), start=1):
        prompt = render_prompt(PROMPT, entities=[_payload(entity) for entity in batch])
        data: Mapping[str, Any] | None = None
        last: LLMError | None = None
        for _attempt in range(2):
            try:
                data = client.complete(
                    system=prompt.system,
                    user=prompt.user,
                    schema=prompt_schema(PROMPT),
                    reasoning_effort=REASONING_EFFORT,
                    tag=reconcile_tag(number),
                ).data
            except LLMRunHalted:
                raise
            except LLMError as exc:
                last = exc
                continue
            break
        if data is None:
            reason = f"{type(last).__name__}: {last} (after one re-attempt)"
            results.update({entity.slug: ReconcileResult(error=reason) for entity in batch})
            continue
        answers: dict[str, Mapping[str, Any]] = {}
        for entry in data["entities"]:
            answers.setdefault(entry["slug"], entry)
        for entity in batch:
            results[entity.slug] = check_answer(entity, answers.get(entity.slug))
    return results
