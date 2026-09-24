"""Dismissal records (``ai/dismissals.jsonl``) and re-applying them to a review.

The ``/dismiss`` job appends one JSON line per dismissal on ``main``; the review runner
reads the same file, so the line shape is a contract::

    {"key": "f-xxxxxxxx", "passages": [names], "hashes": [content hashes], "by": login,
     "pr": number, "at": "YYYY-MM-DDTHH:MM:SSZ", "reason": text}

``passages`` and ``hashes`` come from the finding in the pull request's last
``ai-review.json``, in the finding's passage order, so the dismissal lapses once a cited
passage changes. Without that artifact, or when the key is not in it, nothing is
recorded: a key-only record would suppress the finding forever, so every line has
non-empty ``passages`` and ``hashes`` of equal length.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nanoif.errors import NanoifError

RECORD_KEYS = ("key", "passages", "hashes", "by", "pr", "at", "reason")


class DismissalError(NanoifError):
    """A dismissal cannot be recorded, or the dismissals file is unreadable."""


def find_finding(review: Mapping[str, Any], key: str) -> dict[str, Any] | None:
    """Return the finding with ``key`` from any editor list, or ``None``."""
    for editor in review.get("editors", []):
        for bucket in ("findings", "suppressed", "unverified"):
            for finding in editor.get(bucket, []):
                if finding.get("key") == key:
                    return finding
    return None


def build_record(
    key: str,
    by: str,
    pr: int,
    reason: str | None,
    review: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build one ``ai/dismissals.jsonl`` record.

    Args:
        key: The finding key (``f-xxxxxxxx``).
        by: Login of the collaborator who dismissed it.
        pr: Pull request number.
        reason: Optional free-text reason.
        review: The PR's last ``ai-review.json``.
        now: Timestamp override for tests.

    Returns:
        The record.

    Raises:
        DismissalError: If the review has no finding with ``key``.
    """
    at = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    finding = find_finding(review, key)
    if finding is None:
        raise DismissalError(f"no finding {key} in the last AI review of this pull request")
    return {
        "key": key,
        "passages": [p["name"] for p in finding["passages"]],
        "hashes": [p["hash"] for p in finding["passages"]],
        "by": by,
        "pr": pr,
        "at": at,
        "reason": reason or "",
    }


def append_record(path: Path, record: Mapping[str, Any]) -> None:
    """Append one record as a JSON line, creating the file if needed.

    Args:
        path: ``ai/dismissals.jsonl``.
        record: The record.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_bytes() if path.exists() else b""
    prefix = b"\n" if existing and not existing.endswith(b"\n") else b""
    line = json.dumps(dict(record), sort_keys=True, ensure_ascii=False).encode("utf-8")
    with path.open("ab") as handle:
        handle.write(prefix + line + b"\n")


def load_dismissals(path: Path) -> list[dict[str, Any]]:
    """Read every dismissal record.

    Args:
        path: ``ai/dismissals.jsonl``. A missing file means no dismissals yet.

    Returns:
        The records in file order.

    Raises:
        DismissalError: If a line is not a JSON object with a ``key``.
    """
    if not path.exists():
        return []
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DismissalError(f"{path}:{number}: not JSON: {exc}") from exc
        if not isinstance(record, dict) or not isinstance(record.get("key"), str):
            raise DismissalError(f"{path}:{number}: expected an object with a key")
        records.append(record)
    return records


def _matches(record: Mapping[str, Any], finding: Mapping[str, Any]) -> bool:
    if record.get("key") != finding.get("key"):
        return False
    names, hashes = record.get("passages") or [], record.get("hashes") or []
    if not names or len(names) != len(hashes):
        return False  # not a valid contract line; never suppress on key alone
    recorded = dict(zip(names, hashes, strict=True))
    current = {p["name"]: p["hash"] for p in finding.get("passages", [])}
    return recorded == current


def apply_dismissals(
    review: Mapping[str, Any], dismissals: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Move findings matched by a dismissal into ``suppressed``.

    A dismissal matches when its key equals the finding's key and every cited passage
    still has the recorded content hash.

    Args:
        review: An ``ai-review.json`` document.
        dismissals: Records from :func:`load_dismissals`.

    Returns:
        A new review document; the input is not modified.
    """
    records = list(dismissals)
    result = copy.deepcopy(dict(review))
    for editor in result.get("editors", []):
        kept, moved = [], []
        for finding in editor.get("findings", []):
            target = moved if any(_matches(r, finding) for r in records) else kept
            target.append(finding)
        editor["findings"] = kept
        editor["suppressed"] = list(editor.get("suppressed", [])) + moved
    return result
