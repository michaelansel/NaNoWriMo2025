"""Parser for ``story-overrides.txt``, the writer-editable Story Bible overrides.

One override per line, ``directive: payload``. Blank lines and lines whose
first non-blank character is ``#`` are ignored. Directives:

- ``alias``: two names for the same entity.
- ``not-entity``: a word the extractor must not treat as an entity.
- ``pin``: a fact the Story Bible must keep.
- ``intentional-conflict``: a contradiction the writers meant.

This module checks only the line format; what each payload means is decided
by the Story Bible (Phase 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DIRECTIVES = frozenset({"alias", "not-entity", "pin", "intentional-conflict"})
_LINE_RE = re.compile(r"^(?P<directive>[A-Za-z][A-Za-z-]*)\s*:\s*(?P<payload>.*?)\s*$")


@dataclass(frozen=True)
class Override:
    """One override.

    Attributes:
        directive: One of :data:`DIRECTIVES`.
        payload: Everything after the colon, stripped.
        line: 1-based line number.
    """

    directive: str
    payload: str
    line: int


@dataclass(frozen=True)
class OverrideError:
    """A line that is not a valid override.

    Attributes:
        line: 1-based line number.
        message: What is wrong.
    """

    line: int
    message: str


def parse_overrides(text: str) -> tuple[list[Override], list[OverrideError]]:
    """Parse the overrides file.

    Args:
        text: File contents.

    Returns:
        The valid overrides and one error per invalid line.
    """
    overrides: list[Override] = []
    errors: list[OverrideError] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE_RE.match(line)
        if match is None:
            errors.append(OverrideError(number, "expected `directive: payload`"))
            continue
        directive = match.group("directive")
        if directive not in DIRECTIVES:
            known = ", ".join(sorted(DIRECTIVES))
            message = f"unknown directive {directive!r} (known: {known})"
            errors.append(OverrideError(number, message))
            continue
        if not match.group("payload"):
            errors.append(OverrideError(number, f"{directive}: needs a payload after the colon"))
            continue
        overrides.append(Override(directive, match.group("payload"), number))
    return overrides, errors
