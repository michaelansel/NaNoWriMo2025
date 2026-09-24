"""Parse the slash commands collaborators type in pull-request comments.

Grammar (first line of the comment only, command name case-insensitive)::

    /check-continuity                 review changed passages
    /check-continuity all             review every passage
    /check-continuity passage=<name>  review one passage (the name may contain spaces)
    /extract-story-bible              Story Bible extraction (Phase 3)
    /dismiss f-xxxxxxxx [reason]      record a dismissal of one finding key

Anything else is not a command and parses to ``None``. A known command with bad
arguments parses to a :class:`Command` carrying ``error`` so the workflow can reply
with the usage instead of doing nothing silently.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from pathlib import Path

CHECK = "check-continuity"
EXTRACT = "extract-story-bible"
DISMISS = "dismiss"

CHECK_USAGE = "/check-continuity [all] [passage=<name>]"
DISMISS_USAGE = "/dismiss f-xxxxxxxx [reason]"
MAX_REASON_CHARS = 500
MAX_PASSAGE_CHARS = 200

_KEY = re.compile(r"^f-[0-9a-f]{8}$")
_HEAD = re.compile(r"^/(?P<name>[A-Za-z][\w-]*)(?:\s+(?P<rest>.*))?$")


@dataclass(frozen=True)
class Command:
    """One parsed slash command.

    Attributes:
        name: ``check-continuity``, ``extract-story-bible`` or ``dismiss``.
        mode: For ``check-continuity``: ``changed``, ``all`` or ``passage``.
        passage: The passage name for ``mode == "passage"``.
        key: The finding key for ``dismiss``.
        reason: The optional dismissal reason.
        error: Set when the command is known but its arguments are not; nothing runs.
    """

    name: str
    mode: str | None = None
    passage: str | None = None
    key: str | None = None
    reason: str | None = None
    error: str | None = None

    def outputs(self) -> dict[str, str]:
        """Return the command as ``GITHUB_OUTPUT`` values (empty string for unset)."""
        return {
            "command": self.name,
            "mode": self.mode or "",
            "passage": self.passage or "",
            "key": self.key or "",
            "reason": self.reason or "",
            "error": self.error or "",
        }


def _parse_check(rest: str) -> Command:
    passage: str | None = None
    words = rest
    if "passage=" in rest:
        words, _, passage = rest.partition("passage=")
        passage = passage.strip().strip("\"'").strip()
        if not passage:
            return Command(CHECK, error=f"passage= needs a passage name; usage: {CHECK_USAGE}")
        if len(passage) > MAX_PASSAGE_CHARS:
            return Command(CHECK, error="passage name is too long")
    tokens = words.split()
    unknown = [token for token in tokens if token.lower() != "all"]
    if unknown:
        return Command(CHECK, error=f"unknown argument {unknown[0]!r}; usage: {CHECK_USAGE}")
    if passage is not None:
        if tokens:
            return Command(CHECK, error=f"use either all or passage=, not both; {CHECK_USAGE}")
        return Command(CHECK, mode="passage", passage=passage)
    return Command(CHECK, mode="all" if tokens else "changed")


def _parse_dismiss(rest: str) -> Command:
    key, _, reason = rest.strip().partition(" ")
    key = key.lower()
    if not _KEY.match(key):
        shown = key or "nothing"
        return Command(DISMISS, error=f"{shown!r} is not a finding key; usage: {DISMISS_USAGE}")
    reason = reason.strip()[:MAX_REASON_CHARS]
    return Command(DISMISS, key=key, reason=reason or None)


def parse_command(body: str | None) -> Command | None:
    """Parse the first line of a comment as a slash command.

    Args:
        body: The comment body.

    Returns:
        The command, or ``None`` when the comment is not one of ours.
    """
    if not body:
        return None
    first = body.strip().splitlines()[0].strip() if body.strip() else ""
    match = _HEAD.match(first)
    if not match:
        return None
    name = match.group("name").lower()
    rest = match.group("rest") or ""
    if name == CHECK:
        return _parse_check(rest)
    if name == EXTRACT:
        return Command(EXTRACT)
    if name == DISMISS:
        return _parse_dismiss(rest)
    return None


def write_github_output(path: Path, values: dict[str, str]) -> None:
    """Append values to a ``GITHUB_OUTPUT`` file using random heredoc delimiters.

    A random delimiter means a value (a user's dismissal reason) cannot end its own
    block early and inject another output.

    Args:
        path: The ``GITHUB_OUTPUT`` file.
        values: Output names and values.
    """
    with path.open("a", encoding="utf-8") as handle:
        for name, value in values.items():
            delimiter = f"EOF_{secrets.token_hex(8)}"
            handle.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
