"""The formatting bot's commit on a pull request branch (ADR-025).

The ``format`` job commits what ``nanoif lint --fix`` changed as one commit whose message
:func:`commit_message` writes; the Build comment of the rebuilt head reads it back with
:func:`parse_format_commit`. Both live here so the subject has one definition.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from nanoif.errors import BuildError

TRAILER = "Nanoif-Format"
"""The trailer naming the head the bot's commit was made on; also the loop guard's key."""

_SHA = re.compile(r"^[0-9a-f]{40}$")
_FILE = r"[A-Za-z]{1,10}-\d{8}\.twee"
_SUBJECT = re.compile(
    rf"^style: fix (?P<count>[1-9]\d*) formatting issues? in (?P<files>{_FILE}(?:, {_FILE})*)$"
)
_TRAILER_LINE = re.compile(rf"^{TRAILER}: (?P<sha>[0-9a-f]{{40}})$", re.MULTILINE)


@dataclass(frozen=True)
class FormatCommit:
    """What a formatting commit says it did.

    Attributes:
        count: Issues fixed.
        files: The prose files it changed, by file name.
        previous_sha: The head it was made on (its ``Nanoif-Format`` trailer).
    """

    count: int
    files: tuple[str, ...]
    previous_sha: str


def commit_message(summary: Mapping[str, Any], previous_sha: str) -> str:
    """Write the formatting commit's message from a ``lint_fix`` summary.

    Args:
        summary: The ``lint_fix`` artifact of ``nanoif lint --fix``.
        previous_sha: The pull request head the fix was made on.

    Returns:
        ``style: fix N formatting issues in <files>``, a line saying what kind of change it
        is, and the trailer ``Nanoif-Format: <previous_sha>``.

    Raises:
        BuildError: If nothing was fixed or ``previous_sha`` is not a full commit sha.
    """
    if not _SHA.match(previous_sha):
        raise BuildError(f"{previous_sha!r} is not a full commit sha")
    count = int(summary["total"])
    files = [PurePosixPath(item["file"]).name for item in summary["files"] if item["fixed"]]
    if count < 1 or not files:
        raise BuildError("nothing was fixed, so there is nothing to commit")
    issues = "issue" if count == 1 else "issues"
    return (
        f"style: fix {count} formatting {issues} in {', '.join(files)}\n\n"
        "Whitespace and quote marks only; no word, passage name or link changed.\n\n"
        f"{TRAILER}: {previous_sha}\n"
    )


def parse_format_commit(message: str) -> FormatCommit | None:
    """Read a formatting commit's message back.

    Args:
        message: A commit message (``git log -1 --format=%B``).

    Returns:
        What it says it did, or None for any other commit.
    """
    lines = message.splitlines()
    subject = _SUBJECT.match(lines[0]) if lines else None
    trailer = _TRAILER_LINE.search(message)
    if subject is None or trailer is None:
        return None
    return FormatCommit(
        int(subject.group("count")),
        tuple(subject.group("files").split(", ")),
        trailer.group("sha"),
    )
