"""Names, slugs and ids of the Story Bible (ADR-020).

- An entity slug is ``slugify(name)`` at creation, with ``-2``, ``-3``... on collision, and
  never changes. ``world`` is reserved for rules that belong to no other entity.
- A fact id is ``<slug>#<n>`` with ``n`` taken from the entity's ``next_n`` and never
  reused; a pinned fact is ``<slug>#pin-<first 8 hex of sha256(claim)>``.
- A conflict id is ``c-<slug>-<n>``.

:func:`normalize_name` is the bible's name matcher. The eval scorer keeps its own
normalizer on purpose, so the judge stays independent of the code it judges.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection

WORLD_SLUG = "world"
"""Reserved slug of the entity holding world rules that belong to no other entity."""

QUANTIFIERS = frozenset(
    """
    no some any every each all none one two three four five six seven eight nine ten eleven
    twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty
    """.split()
)
"""A name whose first normalized word is one of these (or a number) is not an entity."""

_APOSTROPHES = str.maketrans({"‘": "'", "’": "'"})
_ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+")
_POSSESSIVE_RE = re.compile(r"(?<=\w)'s\b|(?<=s)'(?=\s|$)")
_NON_WORD_RE = re.compile(r"[^\w\s]+")
_SPACE_RE = re.compile(r"\s+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    """
    a an and are as at be by for from had has have he her his in is it its of on or she that
    the their there this to was were with
    """.split()
)


def normalize_name(name: str) -> str:
    """Return the comparable form of an entity name or alias.

    Case-folded, typographic apostrophes made plain, a leading article and possessives
    dropped, punctuation turned into spaces, whitespace collapsed.

    Args:
        name: A name as written.

    Returns:
        For example ``"widow kestle"`` for ``"The Widow Kestle"``.
    """
    key = _SPACE_RE.sub(" ", name.casefold().translate(_APOSTROPHES)).strip()
    key = _ARTICLE_RE.sub("", key)
    key = _POSSESSIVE_RE.sub("", key)
    key = _NON_WORD_RE.sub(" ", key)
    return _SPACE_RE.sub(" ", key).strip()


def is_generic_name(name: str) -> bool:
    """Return whether a name starts with a quantifier or number word (``no one``).

    Args:
        name: A name as written.

    Returns:
        True when the first normalized word is in :data:`QUANTIFIERS` or has a digit.
    """
    words = normalize_name(name).split()
    if not words:
        return True
    first = words[0]
    return first in QUANTIFIERS or any(char.isdigit() for char in first)


def slugify(name: str) -> str:
    """Return the slug form of a name.

    Args:
        name: A name as written.

    Returns:
        Lower-case ASCII words joined by ``-``; ``"entity"`` when nothing is left.
    """
    slug = _SLUG_RE.sub("-", name.casefold().translate(_APOSTROPHES).replace("'", "")).strip("-")
    return slug or "entity"


def entity_slug(name: str, taken: Collection[str]) -> str:
    """Return a new entity's slug, unique among ``taken`` and never the reserved ``world``.

    Args:
        name: The entity's name.
        taken: Slugs already in use (live, merged or retired).

    Returns:
        ``slugify(name)``, or it with ``-2``, ``-3``... appended on collision.
    """
    base = slugify(name)
    used = set(taken) | {WORLD_SLUG}
    if base not in used:
        return base
    n = 2
    while f"{base}-{n}" in used:
        n += 1
    return f"{base}-{n}"


def fact_id(slug: str, n: int) -> str:
    """Return the id of an entity's ``n``-th fact.

    Args:
        slug: The entity slug.
        n: The number taken from the entity's ``next_n``.

    Returns:
        ``<slug>#<n>``.
    """
    return f"{slug}#{n}"


def fact_number(fact: str) -> int:
    """Return ``n`` of a ``<slug>#<n>`` fact id, or ``0`` for a pinned fact.

    Args:
        fact: A fact id.

    Returns:
        The number, for "newest first" ordering.
    """
    _slug, _hash, tail = fact.rpartition("#")
    return int(tail) if tail.isdigit() else 0


def pin_fact_id(slug: str, claim: str) -> str:
    """Return the id of a pinned fact.

    Args:
        slug: The entity slug.
        claim: The pinned claim, as written in ``story-overrides.txt``.

    Returns:
        ``<slug>#pin-<first 8 hex of sha256(claim)>``.
    """
    digest = hashlib.sha256(claim.encode("utf-8")).hexdigest()[:8]
    return f"{slug}#pin-{digest}"


def conflict_id(slug: str, taken: Collection[str]) -> str:
    """Return the next unused conflict id for an entity.

    Args:
        slug: The entity slug.
        taken: Every conflict id in the cache (open or retired), so none is reused.

    Returns:
        ``c-<slug>-<n>`` with ``n`` one more than the highest in use for this slug.
    """
    prefix = f"c-{slug}-"
    numbers = [
        int(existing[len(prefix) :])
        for existing in taken
        if existing.startswith(prefix) and existing[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1}"


def claim_tokens(text: str) -> set[str]:
    """Return a claim's content words: case-folded, stopwords dropped.

    Args:
        text: A claim.

    Returns:
        The token set.
    """
    return {word for word in _TOKEN_RE.findall(text.casefold()) if word not in _STOPWORDS}


def claim_overlap(a: str, b: str) -> float:
    """Return the shared content words of two claims over the larger claim's count.

    Args:
        a: One claim.
        b: The other.

    Returns:
        A value in ``[0, 1]``; ``0`` when either claim has no content words.
    """
    left, right = claim_tokens(a), claim_tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left), len(right))
