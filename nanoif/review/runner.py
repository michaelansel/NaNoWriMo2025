"""``nanoif ai review``: run the editors over their units and build the ``ai_review`` artifact.

Honesty rules the runner enforces:

- each unit gets one application-level re-attempt after an ``LLMError``, then status
  ``error`` with the reason;
- a unit still over budget after truncation is ``skipped: too long (N tokens)``;
- an ``LLMRunHalted`` (per-job token budget, monthly spend cap, unreadable spend ledger)
  stops further units, which become ``skipped`` with the halt's reason; a run whose
  spend check fails before it starts skips every editor with that reason and calls no
  model;
- an editor is ``ok`` only when every unit was reviewed, ``error`` when any unit was not,
  and ``skipped`` (with a reason) when it could not start;
- the verdict is computed from the units, never taken from the model.
"""

from __future__ import annotations

import json
import os
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from nanoif.build.paths import ProjectPaths
from nanoif.errors import ReviewConfigError
from nanoif.git.service import GitService
from nanoif.llm.client import Completer, LLMClient
from nanoif.llm.errors import BUDGET_EXHAUSTED_REASON, LLMError, LLMRunHalted
from nanoif.llm.ledger import spend_line
from nanoif.llm.profiles import DEFAULT_MAX_CONCURRENCY, Settings
from nanoif.review import continuity, style
from nanoif.review.findings import Finding, UnitFindings, is_dismissed, merge_findings
from nanoif.review.units import (
    ReviewStory,
    ReviewUnit,
    continuity_units,
    load_story,
    select_passages,
    style_unit,
    unit_budget,
)
from nanoif.schemas.artifacts import load_artifact, validate_artifact

EDITORS: tuple[str, ...] = ("continuity", "style")
RUNNER_ENV = "NANOIF_RUNNER"
RUNNERS = ("exe", "hosted", "local")
DEFAULT_RUNNER = "local"
BUDGET_EXHAUSTED = BUDGET_EXHAUSTED_REASON
ARTIFACT_VERSION = 1

UnitStatus = Literal["reviewed", "error", "skipped"]
EditorCall = Callable[[Completer, ReviewStory, ReviewUnit], UnitFindings]

_EDITOR_CALLS: dict[str, EditorCall] = {
    "continuity": continuity.review_unit,
    "style": style.review_unit,
}


@dataclass(frozen=True)
class UnitOutcome:
    """How one unit went.

    Attributes:
        status: ``reviewed``, ``error`` or ``skipped``.
        reason: Why it was not reviewed, or coverage notes for a reviewed unit.
        result: The post-processed findings when reviewed.
    """

    status: UnitStatus
    reason: str | None
    result: UnitFindings | None = None


def runner_name(env: Mapping[str, str]) -> str:
    """Return where this job runs, from ``NANOIF_RUNNER``.

    Args:
        env: Environment mapping.

    Returns:
        ``exe``, ``hosted`` or ``local`` (the default).

    Raises:
        ReviewConfigError: The variable holds another value.
    """
    value = env.get(RUNNER_ENV, "").strip() or DEFAULT_RUNNER
    if value not in RUNNERS:
        raise ReviewConfigError(f"{RUNNER_ENV} {value!r} not in {RUNNERS}")
    return value


def load_dismissals(path: Path) -> dict[str, list[dict[str, str]]]:
    """Read ``ai/dismissals.jsonl`` into key to recorded passage hashes.

    Each line is ``{"key": "f-...", "passages": [names], "hashes": ...}`` where ``hashes``
    is either ``{name: hash}`` or a list aligned with ``passages``.

    Args:
        path: The dismissals file; a missing file means no dismissals.

    Returns:
        Key to the list of ``{passage name: hash}`` maps recorded for it.

    Raises:
        ReviewConfigError: A line is not valid JSON or lacks a key or usable hashes.
    """
    if not path.is_file():
        return {}
    dismissals: dict[str, list[dict[str, str]]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReviewConfigError(f"{path}:{number}: not valid JSON ({exc.msg})") from exc
        if not isinstance(record, dict) or not isinstance(record.get("key"), str):
            raise ReviewConfigError(f"{path}:{number}: a dismissal needs a string 'key'")
        hashes = record.get("hashes")
        passages = record.get("passages")
        if isinstance(hashes, list) and isinstance(passages, list) and len(hashes) == len(
            passages
        ):
            hashes = dict(zip(passages, hashes, strict=True))
        if not isinstance(hashes, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in hashes.items()
        ):
            raise ReviewConfigError(
                f"{path}:{number}: 'hashes' must map passage names to content hashes"
            )
        dismissals.setdefault(record["key"], []).append(hashes)
    return dismissals


class _Halt:
    """The first run-halting reason seen by any unit; later units skip with it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reason: str | None = None

    def set(self, reason: str) -> None:
        with self._lock:
            if self.reason is None:
                self.reason = reason


def _run_unit(
    client: Completer,
    story: ReviewStory,
    editor: str,
    unit: ReviewUnit,
    halt: _Halt,
) -> UnitOutcome:
    if unit.over_budget:
        return UnitOutcome("skipped", f"too long ({unit.tokens} tokens)")
    call = _EDITOR_CALLS[editor]
    last: LLMError | None = None
    for _attempt in range(2):
        if halt.reason is not None:
            return UnitOutcome("skipped", halt.reason)
        try:
            result = call(client, story, unit)
        except LLMRunHalted as exc:
            halt.set(exc.reason)
            return UnitOutcome("skipped", halt.reason or exc.reason)
        except LLMError as exc:
            last = exc
            continue
        notes = [note for note in (unit.note,) if note]
        if result.dropped:
            notes.append(f"{result.dropped} malformed finding(s) discarded")
        return UnitOutcome("reviewed", "; ".join(notes) or None, result)
    return UnitOutcome("error", f"{type(last).__name__}: {last} (after one re-attempt)")


def _plan(
    editor: str, story: ReviewStory, names: Sequence[str], budget: int
) -> tuple[str | None, list[ReviewUnit]]:
    if editor == "continuity":
        return None, [unit for name in names for unit in continuity_units(story, name, budget)]
    if story.style.problem is not None:
        return story.style.problem, []
    return None, [style_unit(story, name, budget) for name in names]


def _findings_block(
    outcomes: Sequence[UnitOutcome], dismissals: Mapping[str, Sequence[Mapping[str, str]]]
) -> tuple[list[Finding], list[Finding], list[Finding]]:
    results = [outcome.result for outcome in outcomes if outcome.result is not None]
    merged = merge_findings(result.findings for result in results)
    verified_keys = {finding.key for finding in merged}
    unverified = [
        finding
        for finding in merge_findings(result.unverified for result in results)
        if finding.key not in verified_keys
    ]
    shown = [finding for finding in merged if not is_dismissed(finding, dismissals)]
    suppressed = [finding for finding in merged if is_dismissed(finding, dismissals)]
    return shown, suppressed, unverified


def editor_status(units: Sequence[Mapping[str, Any]]) -> tuple[str, str | None]:
    """Compute an editor's ``status`` and ``reason`` from its unit entries.

    Used by the runner and by the merge of a single-passage re-check into an earlier
    review, so both state coverage the same way.

    Args:
        units: The editor's ``units`` entries (``status`` and ``reason`` are read).

    Returns:
        ``("ok", None)`` when every unit was reviewed, ``("ok", "no passages to review")``
        for no units, else ``("error", "N of M unit(s) not reviewed (<causes>)")``.
    """
    missed = [unit for unit in units if unit["status"] != "reviewed"]
    if not units:
        return "ok", "no passages to review"
    if not missed:
        return "ok", None
    causes = Counter(
        "error" if unit["status"] == "error" else (unit.get("reason") or "skipped")
        for unit in missed
    )
    detail = ", ".join(f"{count} {cause}" for cause, count in sorted(causes.items()))
    return "error", f"{len(missed)} of {len(units)} unit(s) not reviewed ({detail})"


def _editor_entry(
    name: str,
    skip_reason: str | None,
    units: Sequence[ReviewUnit],
    outcomes: Sequence[UnitOutcome],
    dismissals: Mapping[str, Sequence[Mapping[str, str]]],
) -> dict[str, Any]:
    if skip_reason is not None:
        return {
            "name": name,
            "status": "skipped",
            "reason": skip_reason,
            "units": [],
            "findings": [],
            "suppressed": [],
            "unverified": [],
        }
    shown, suppressed, unverified = _findings_block(outcomes, dismissals)
    unit_entries = [
        {
            "passage": unit.passage,
            "status": outcome.status,
            "reason": outcome.reason,
            "tokens": unit.tokens,
        }
        for unit, outcome in zip(units, outcomes, strict=True)
    ]
    status, reason = editor_status(unit_entries)
    return {
        "name": name,
        "status": status,
        "reason": reason,
        "units": unit_entries,
        "findings": [finding.to_dict() for finding in shown],
        "suppressed": [finding.to_dict() for finding in suppressed],
        "unverified": [finding.to_dict() for finding in unverified],
    }


def review(
    repo: Path,
    mode: str,
    passage: str | None = None,
    editors: Sequence[str] = EDITORS,
    client: Completer | None = None,
    dismissals_path: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    max_workers: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run the editors and return the ``ai_review`` artifact.

    Args:
        repo: Repository root with ``lib/artifacts/story_graph.json`` (and, for mode
            ``changed``, ``dist/changes.json``) already built.
        mode: ``changed``, ``all`` or ``passage``.
        passage: The passage for mode ``passage``.
        editors: Editors to run, in output order.
        client: The completer; defaults to ``LLMClient(Settings.from_env())``.
        dismissals_path: Defaults to ``<repo>/ai/dismissals.jsonl``.
        env: Environment for ``NANOIF_RUNNER``, ``NANOIF_REVIEW_UNIT_BUDGET`` and the LLM
            settings; defaults to ``os.environ``.
        max_workers: Concurrent units; defaults to the client's ``max_concurrency``.
        now: Timestamp for ``generated_at``.

    Returns:
        The artifact, validated against ``ai_review``.

    Raises:
        ReviewConfigError: Bad mode, passage, editor list, runner, budget, or dismissals.
        LLMConfigError: No client given and the LLM settings are unusable.
        BuildError: A required build artifact is missing.
        GitError: The repository has no ``HEAD`` commit.
    """
    env = os.environ if env is None else env
    unknown = [name for name in editors if name not in EDITORS]
    if unknown or not editors:
        raise ReviewConfigError(f"editors must be a non-empty subset of {EDITORS}, got {unknown}")
    runner = runner_name(env)
    budget = unit_budget(env)
    paths = ProjectPaths.from_repo(Path(repo))
    if client is None:
        settings = Settings.from_env(env)
        client = LLMClient(settings)
        workers = max_workers or settings.max_concurrency
    else:
        configured = getattr(getattr(client, "settings", None), "max_concurrency", None)
        workers = max_workers or configured or DEFAULT_MAX_CONCURRENCY

    story = load_story(paths)
    changes_path = paths.dist / "changes.json"
    changes = load_artifact(changes_path, "changes") if changes_path.is_file() else None
    names = select_passages(story, mode, changes, passage)
    dismissals = load_dismissals(dismissals_path or paths.repo / "ai" / "dismissals.jsonl")
    commit_sha = GitService(paths.repo).rev_parse("HEAD")

    try:
        client.check_spend()
    except LLMRunHalted as exc:
        plans = {name: (exc.reason, []) for name in editors}
    else:
        plans = {name: _plan(name, story, names, budget) for name in editors}
    jobs = [(name, unit) for name in editors for unit in plans[name][1]]
    halt = _Halt()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [
            pool.submit(_run_unit, client, story, name, unit, halt) for name, unit in jobs
        ]
        outcomes = [future.result() for future in futures]

    entries = []
    cursor = 0
    for name in editors:
        skip_reason, units = plans[name]
        mine = outcomes[cursor : cursor + len(units)]
        cursor += len(units)
        entries.append(_editor_entry(name, skip_reason, units, mine, dismissals))

    stamp = (now or datetime.now(UTC)).astimezone(UTC)
    artifact = {
        "version": ARTIFACT_VERSION,
        "generated_at": stamp.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "commit_sha": commit_sha,
        "base_sha": changes["base_sha"] if changes is not None else None,
        "mode": mode,
        "llm": {**client.usage_summary(), "runner": runner},
        "editors": entries,
    }
    validate_artifact(artifact, "ai_review")
    return artifact


def summary_lines(artifact: Mapping[str, Any]) -> list[str]:
    """One line per editor for the CLI and step summaries.

    Args:
        artifact: An ``ai_review`` artifact.

    Returns:
        Lines such as ``continuity: ok, 13 of 13 units reviewed, 2 finding(s), ...``, then
        the monthly spend line when the client keeps a spend ledger.
    """
    lines = []
    for editor in artifact["editors"]:
        if editor["status"] == "skipped":
            lines.append(f"{editor['name']}: skipped ({editor['reason']})")
            continue
        units = editor["units"]
        reviewed = sum(1 for unit in units if unit["status"] == "reviewed")
        line = (
            f"{editor['name']}: {editor['status']}, {reviewed} of {len(units)} units reviewed, "
            f"{len(editor['findings'])} finding(s), {len(editor['suppressed'])} suppressed, "
            f"{len(editor['unverified'])} unverified"
        )
        if editor["reason"]:
            line += f" ({editor['reason']})"
        lines.append(line)
    if spend := spend_line(artifact["llm"]):
        lines.append(spend)
    return lines
