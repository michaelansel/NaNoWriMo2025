"""Merge a ``/check-continuity passage=<name>`` result into the PR's last full review.

A single-passage re-check reviews one passage, so rendering it alone would replace each
editor's comment and check run with that passage's result and could turn a check green
while other changed passages still have findings. The re-check is merged into the pull
request's last ``ai-review.json`` artifact instead: the re-checked passage's units and
findings are replaced, everything else is kept, and the merged artifact is rendered and
uploaded as the new last review (so ``/dismiss`` still finds every key).

The earlier review is used only when it was made for the same pull-request head commit,
recorded next to it in the artifact as :data:`HEAD_SHA_FILE`; otherwise its results may
not match the passages as they are now. Without a usable earlier review the re-check is
published alone with ``mode: passage``, which the reporter labels partial and never
reports as ``success``.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from nanoif.review.runner import editor_status
from nanoif.schemas.artifacts import validate_artifact

HEAD_SHA_FILE = "ai-review-head-sha.txt"
BUCKETS = ("findings", "suppressed", "unverified")


def _passage_names(finding: Mapping[str, Any]) -> set[str]:
    return {passage["name"] for passage in finding["passages"]}


def _merge_units(
    previous: list[dict[str, Any]], update: list[dict[str, Any]], passage: str
) -> list[dict[str, Any]]:
    """Replace the passage's units in place (at its first position), else append them."""
    merged: list[dict[str, Any]] = []
    placed = False
    for unit in previous:
        if unit["passage"] != passage:
            merged.append(unit)
        elif not placed:
            merged.extend(update)
            placed = True
    if not placed:
        merged.extend(update)
    return merged


def _merge_editor(
    previous: Mapping[str, Any], update: Mapping[str, Any], passage: str
) -> dict[str, Any]:
    if previous["status"] == "skipped" or update["status"] == "skipped":
        # "skipped" is story-wide (for example no storyStyle); this run's answer is current.
        return copy.deepcopy(dict(update))
    other_units = {unit["passage"] for unit in previous["units"]} - {passage}

    def from_other_unit(finding: Mapping[str, Any]) -> bool:
        # Findings are not tagged with the unit that made them. One that names another
        # reviewed passage may have come from that passage's unit, so it is kept: a
        # merge may show a finding twice over, never hide one.
        names = _passage_names(finding)
        return passage not in names or bool(names & other_units)

    rechecked = {finding["key"] for bucket in BUCKETS for finding in update[bucket]}
    merged: dict[str, Any] = {"name": update["name"]}
    for bucket in BUCKETS:
        kept = [
            finding
            for finding in previous[bucket]
            if from_other_unit(finding) and finding["key"] not in rechecked
        ]
        merged[bucket] = copy.deepcopy(kept + list(update[bucket]))
    verified = {finding["key"] for finding in merged["findings"] + merged["suppressed"]}
    merged["unverified"] = [f for f in merged["unverified"] if f["key"] not in verified]
    merged["units"] = copy.deepcopy(_merge_units(previous["units"], update["units"], passage))
    merged["status"], merged["reason"] = editor_status(merged["units"])
    return {
        key: merged[key]
        for key in ("name", "status", "reason", "units", "findings", "suppressed", "unverified")
    }


def merge_passage_review(
    previous: Mapping[str, Any], update: Mapping[str, Any], passage: str
) -> dict[str, Any]:
    """Merge a single-passage re-check into an earlier review of the same commit.

    Args:
        previous: The pull request's last ``ai-review.json`` (any mode). A ``passage``
            mode review is itself partial, and the merge stays partial.
        update: The re-check (``mode: passage``) of ``passage``.
        passage: The re-checked passage name.

    Returns:
        A new ``ai_review`` artifact: ``previous``'s mode and editors, with every unit of
        ``passage`` and every finding only that passage's unit could have made replaced
        by ``update``'s; ``generated_at``, ``commit_sha``, ``base_sha`` and ``llm`` (the
        cost of this run) from ``update``. Editor status and reason are recomputed from
        the merged units. The inputs are not modified.

    Raises:
        ArtifactValidationError: If the merged artifact does not match its schema.
    """
    updates = {editor["name"]: editor for editor in update["editors"]}
    editors = []
    for editor in previous["editors"]:
        fresh = updates.pop(editor["name"], None)
        editors.append(
            copy.deepcopy(dict(editor)) if fresh is None else _merge_editor(editor, fresh, passage)
        )
    editors.extend(copy.deepcopy(dict(editor)) for editor in updates.values())
    merged = copy.deepcopy(dict(update))
    merged["mode"] = previous["mode"]
    merged["editors"] = editors
    validate_artifact(merged, "ai_review")
    return merged
