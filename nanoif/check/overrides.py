"""The one parser of ``story-overrides.txt``, the writer-editable Story Bible overrides.

One override per line, ``directive: payload``. Blank lines and lines whose first
non-blank character is ``#`` are ignored. Directives and their payloads (ADR-020):

- ``alias: <canonical> = <alias>, <alias>...``: the named entities are one entity.
- ``not-entity: <phrase>``: an entity whose name or alias is this phrase is removed.
- ``pin: <entity> = <claim> | "<quote>" @ <passage>``: a fact the Story Bible always keeps.
- ``intentional-conflict: c-<id>``, a conflict id shown on the page, or
  ``intentional-conflict: <label> = <entity> | <quote fragment>``, a named mystery.

A line whose directive or payload is malformed is an :class:`OverrideError`; ``nanoif
check structure`` reports each one, and the Story Bible ignores it. The Story Bible
consumes :class:`Overrides` and never re-parses the file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from nanoif.errors import BuildError

DIRECTIVES = frozenset({"alias", "not-entity", "pin", "intentional-conflict"})
_LINE_RE = re.compile(r"^(?P<directive>[A-Za-z][A-Za-z-]*)\s*:\s*(?P<payload>.*?)\s*$")
_PIN_RE = re.compile(
    r"^(?P<entity>[^=|]+?)\s*=\s*(?P<claim>[^|]+?)\s*\|\s*"
    r"[\"“](?P<quote>.+)[\"”]\s*@\s*(?P<passage>[^@]+?)$"
)
_MYSTERY_RE = re.compile(r"^(?P<label>[^=|]+?)\s*=\s*(?P<entity>[^|]+?)\s*\|\s*(?P<fragment>.+)$")
_CONFLICT_ID_RE = re.compile(r"^c-[a-z0-9]+(?:-[a-z0-9]+)*$")

ALIAS_FORM = "alias: expected `<canonical> = <alias>, <alias>...`"
PIN_FORM = 'pin: expected `<entity> = <claim> | "<quote>" @ <passage>`'
CONFLICT_FORM = (
    "intentional-conflict: expected `c-<id>` or `<label> = <entity> | <quote fragment>`"
)


@dataclass(frozen=True)
class AliasOverride:
    """``alias:``: every entity named ``canonical`` or one of ``aliases`` is one entity.

    Attributes:
        canonical: The name the merged entity is shown under.
        aliases: Other names of the same entity.
        line: 1-based line number.
    """

    canonical: str
    aliases: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class NotEntityOverride:
    """``not-entity:``: a phrase that is never an entity.

    Attributes:
        phrase: The phrase, as written.
        line: 1-based line number.
    """

    phrase: str
    line: int


@dataclass(frozen=True)
class PinOverride:
    """``pin:``: a fact the Story Bible always shows and the Continuity Editor always sees.

    Attributes:
        entity: The entity's name or alias.
        claim: The fact.
        quote: The verbatim quote backing it.
        passage: The passage the quote is from.
        line: 1-based line number.
    """

    entity: str
    claim: str
    quote: str
    passage: str
    line: int


@dataclass(frozen=True)
class IntentionalConflictOverride:
    """``intentional-conflict:`` in either form.

    Attributes:
        line: 1-based line number.
        conflict_id: The conflict id, for the ``c-<id>`` form.
        label: The mystery's label, for the ``<label> = <entity> | <fragment>`` form.
        entity: The entity the mystery is about (second form).
        fragment: Text a conflicting fact's quote contains (second form).
    """

    line: int
    conflict_id: str | None = None
    label: str | None = None
    entity: str | None = None
    fragment: str | None = None

    @property
    def name(self) -> str:
        """The conflict id or the label: what a suppression reason and the page show."""
        return self.conflict_id or self.label or ""


Payload = AliasOverride | NotEntityOverride | PinOverride | IntentionalConflictOverride


@dataclass(frozen=True)
class Override:
    """One valid override line.

    Attributes:
        directive: One of :data:`DIRECTIVES`.
        payload: Everything after the colon, stripped.
        line: 1-based line number.
        value: The typed payload.
    """

    directive: str
    payload: str
    line: int
    value: Payload


@dataclass(frozen=True)
class OverrideError:
    """A line that is not a valid override.

    Attributes:
        line: 1-based line number.
        message: What is wrong.
    """

    line: int
    message: str


@dataclass(frozen=True)
class Overrides:
    """Every valid override, grouped by directive, plus the lines that were not valid.

    Attributes:
        aliases: ``alias:`` lines in file order.
        not_entities: ``not-entity:`` lines.
        pins: ``pin:`` lines.
        intentional_conflicts: ``intentional-conflict:`` lines.
        errors: Invalid lines (reported by the structure check, ignored by the bible).
    """

    aliases: tuple[AliasOverride, ...] = ()
    not_entities: tuple[NotEntityOverride, ...] = ()
    pins: tuple[PinOverride, ...] = ()
    intentional_conflicts: tuple[IntentionalConflictOverride, ...] = ()
    errors: tuple[OverrideError, ...] = ()

    @classmethod
    def from_text(cls, text: str) -> Overrides:
        """Parse the file's text into typed groups.

        Args:
            text: File contents.

        Returns:
            The grouped overrides.
        """
        overrides, errors = parse_overrides(text)
        values = [override.value for override in overrides]
        return cls(
            aliases=tuple(v for v in values if isinstance(v, AliasOverride)),
            not_entities=tuple(v for v in values if isinstance(v, NotEntityOverride)),
            pins=tuple(v for v in values if isinstance(v, PinOverride)),
            intentional_conflicts=tuple(
                v for v in values if isinstance(v, IntentionalConflictOverride)
            ),
            errors=tuple(errors),
        )


def read_overrides(path: Path) -> Overrides:
    """Read ``story-overrides.txt``; a missing file means no overrides.

    Args:
        path: The overrides file.

    Returns:
        The grouped overrides.

    Raises:
        BuildError: The file exists but cannot be read as UTF-8 text.
    """
    if not path.exists():
        return Overrides()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BuildError(f"story-overrides file is unreadable: {path}: {exc}") from exc
    return Overrides.from_text(text)


def _payload(directive: str, payload: str, line: int) -> Payload | str:
    """Return the typed payload, or the error message for a malformed one."""
    if directive == "not-entity":
        return NotEntityOverride(payload, line)
    if directive == "alias":
        canonical, sep, rest = payload.partition("=")
        aliases = tuple(name.strip() for name in rest.split(",") if name.strip())
        if not sep or not canonical.strip() or not aliases:
            return ALIAS_FORM
        return AliasOverride(canonical.strip(), aliases, line)
    if directive == "pin":
        match = _PIN_RE.match(payload)
        if match is None or not match.group("quote").strip():
            return PIN_FORM
        return PinOverride(
            match.group("entity").strip(),
            match.group("claim").strip(),
            match.group("quote").strip(),
            match.group("passage").strip(),
            line,
        )
    if "=" in payload:
        match = _MYSTERY_RE.match(payload)
        if match is None:
            return CONFLICT_FORM
        return IntentionalConflictOverride(
            line,
            label=match.group("label").strip(),
            entity=match.group("entity").strip(),
            fragment=match.group("fragment").strip(),
        )
    if _CONFLICT_ID_RE.match(payload) is None:
        return CONFLICT_FORM
    return IntentionalConflictOverride(line, conflict_id=payload)


def parse_overrides(text: str) -> tuple[list[Override], list[OverrideError]]:
    """Parse the overrides file.

    Args:
        text: File contents.

    Returns:
        The valid overrides and one error per invalid line (bad format, unknown
        directive, missing or malformed payload).
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
        payload = match.group("payload")
        if not payload:
            errors.append(OverrideError(number, f"{directive}: needs a payload after the colon"))
            continue
        value = _payload(directive, payload, number)
        if isinstance(value, str):
            errors.append(OverrideError(number, value))
            continue
        overrides.append(Override(directive, payload, number, value))
    return overrides, errors
