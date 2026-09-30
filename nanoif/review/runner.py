"""``nanoif ai review``: run the editors over their units and build the ``ai_review`` artifact.

Honesty rules the runner enforces:

- each unit gets one application-level re-attempt after an ``LLMError``, then status
  ``error`` with the reason;
- a unit still over budget after truncation is ``skipped: too long (N tokens)``;
- an ``LLMRunHalted`` (per-job token budget, monthly spend cap, unreadable spend ledger)
  stops further units, which become ``skipped`` with the halt's reason; a run whose
  spend check fails before it starts skips every editor with that reason and calls no
  model. Mode ``all`` checks the cap for its whole :class:`CostEstimate`, so it starts
  only when the estimate fits under the cap; the other modes check only that the cap
  is not already reached, and each call is then checked on its own;
- an editor is ``ok`` only when every unit was reviewed, ``error`` when any unit was not,
  and ``skipped`` (with a reason) when it could not start;
- the verdict is computed from the units, never taken from the model;
- the Continuity Editor reads ``dist/canon-pack.json`` (ADR-020): each unit gets the canon
  slice of its passage, a finding on a fact in an intentional conflict is suppressed with
  the reason, and the artifact's ``canon`` block says which canon was used. A missing or
  invalid pack stops the review; it is never an empty canon.
"""

from __future__ import annotations

import json
import math
import os
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from nanoif.bible.canon import CanonFact, CanonSlice, load_canon_pack, select_canon
from nanoif.bible.source import bible_passages
from nanoif.build.paths import ProjectPaths
from nanoif.errors import ReviewConfigError
from nanoif.git.service import GitService
from nanoif.llm.client import Completer, LLMClient, prompt_token_bound
from nanoif.llm.errors import BUDGET_EXHAUSTED_REASON, LLMError, LLMRunHalted
from nanoif.llm.ledger import spend_line
from nanoif.llm.pricing import cap_rate, cap_usd
from nanoif.llm.profiles import DEFAULT_MAX_CONCURRENCY, REASONING_MIN_MAX_TOKENS, Settings
from nanoif.llm.prompts import Prompt, prompt_schema
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
EditorCall = Callable[[Completer, ReviewStory, ReviewUnit, Sequence[CanonFact]], UnitFindings]

_EDITOR_CALLS: dict[str, EditorCall] = {
    "continuity": continuity.review_unit,
    "style": lambda client, story, unit, _canon: style.review_unit(client, story, unit),
}
_EDITOR_PROMPTS: dict[
    str, Callable[[ReviewStory, ReviewUnit, Sequence[CanonFact]], Prompt]
] = {
    "continuity": continuity.build_prompt,
    "style": lambda story, unit, _canon: style.build_prompt(story, unit),
}
_EDITOR_REQUESTS: dict[str, tuple[str, int]] = {
    "continuity": (continuity.PROMPT, continuity.MAX_TOKENS),
    "style": (style.PROMPT, style.MAX_TOKENS),
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


@dataclass(frozen=True)
class CostEstimate:
    """What a review will cost at most, worked out before any model call.

    Every unit that will be sent is counted as one call whose answer uses its whole
    completion allowance, priced at the rate the monthly cap charges (ADR-023). That is
    the worst case the client reserves for each call, so the run's cost stays within it
    unless a call needs a repair round or a re-attempt, which the cap checks one call
    at a time (AC-continuity-review-32).

    Attributes:
        calls: Model calls planned: one per unit short enough to send.
        prompt_tokens: The client's estimate of their prompt tokens, each output schema
            counted as embedded in the prompt.
        completion_tokens: Their completion allowance (``max_tokens``, as the client
            raises it for reasoning models).
        usd: ``prompt_tokens`` at the input rate plus ``completion_tokens`` at the output
            rate.
        priced: Whether the model has a list price; ``False`` means ``usd`` uses the
            cap's rate for an unpriced model.
        model: The model the rate is for.
    """

    calls: int
    prompt_tokens: int
    completion_tokens: int
    usd: float
    priced: bool
    model: str

    def summary(self) -> str:
        """Return the step-summary line, for example ``estimated cost: at most $2.32 ...``."""
        rate = (
            f"{self.model} list prices"
            if self.priced
            else f"the spend cap's rate for {self.model}, which has no known price"
        )
        return (
            f"estimated cost: at most ${_round_up(self.usd, 2):.2f} for {self.calls} model "
            f"calls ({self.prompt_tokens:,} in / up to {self.completion_tokens:,} out tokens) "
            f"at {rate}"
        )

    def outputs(self) -> dict[str, str]:
        """Return the step outputs ``nanoif github pending`` and ``report`` take."""
        return {
            "estimate_usd": f"{_round_up(self.usd, 4):.4f}",
            "estimate_calls": str(self.calls),
            "estimate_priced": "true" if self.priced else "false",
        }


def _round_up(value: float, places: int) -> float:
    """Round up to ``places`` decimals, so a rounded upper bound stays an upper bound."""
    scale = 10**places
    return math.ceil(round(value * scale, 6)) / scale


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
    canon: Sequence[CanonFact] = (),
) -> UnitOutcome:
    if unit.over_budget:
        return UnitOutcome("skipped", f"too long ({unit.tokens} tokens)")
    call = _EDITOR_CALLS[editor]
    last: LLMError | None = None
    for _attempt in range(2):
        if halt.reason is not None:
            return UnitOutcome("skipped", halt.reason)
        try:
            result = call(client, story, unit, canon)
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


def _suppression(
    finding: Finding,
    dismissals: Mapping[str, Sequence[Mapping[str, str]]],
    intentional: Mapping[str, str],
) -> str | None:
    if finding.canon_fact_id is not None and finding.canon_fact_id in intentional:
        return f"intentional-conflict:{intentional[finding.canon_fact_id]}"
    if is_dismissed(finding, dismissals):
        return "dismissed"
    return None


def _findings_block(
    outcomes: Sequence[UnitOutcome],
    dismissals: Mapping[str, Sequence[Mapping[str, str]]],
    intentional: Mapping[str, str],
) -> tuple[list[Finding], list[Finding], list[Finding]]:
    results = [outcome.result for outcome in outcomes if outcome.result is not None]
    merged = merge_findings(result.findings for result in results)
    verified_keys = {finding.key for finding in merged}
    unverified = [
        finding
        for finding in merge_findings(result.unverified for result in results)
        if finding.key not in verified_keys
    ]
    shown: list[Finding] = []
    suppressed: list[Finding] = []
    for finding in merged:
        reason = _suppression(finding, dismissals, intentional)
        if reason is None:
            shown.append(finding)
        else:
            suppressed.append(replace(finding, suppressed_reason=reason))
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
    intentional: Mapping[str, str] | None = None,
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
    shown, suppressed, unverified = _findings_block(outcomes, dismissals, intentional or {})
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


@dataclass(frozen=True)
class _Setup:
    """Everything a review works out before calling a model."""

    mode: str
    editors: tuple[str, ...]
    client: Completer
    workers: int
    runner: str
    budget: int
    story: ReviewStory
    names: list[str]
    changes: dict[str, Any] | None
    dismissals: dict[str, list[dict[str, str]]]
    commit_sha: str
    slices: dict[str, CanonSlice]
    canon_block: dict[str, Any] | None

    @property
    def intentional(self) -> dict[str, str]:
        return {
            fid: label for piece in self.slices.values() for fid, label in piece.intentional.items()
        }

    def plans(self) -> dict[str, tuple[str | None, list[ReviewUnit]]]:
        return {name: _plan(name, self.story, self.names, self.budget) for name in self.editors}

    def canon_for(self, editor: str, unit: ReviewUnit) -> Sequence[CanonFact]:
        return self.slices[unit.passage].facts if editor == "continuity" else ()


def _setup(
    repo: Path,
    mode: str,
    passage: str | None,
    editors: Sequence[str],
    client: Completer | None,
    dismissals_path: Path | None,
    env: Mapping[str, str] | None,
    max_workers: int | None,
    canon_path: Path | None,
) -> _Setup:
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
    slices: dict[str, CanonSlice] = {}
    canon_block: dict[str, Any] | None = None
    if "continuity" in editors:
        slices, canon_block = _canon(paths, story, names, canon_path or paths.canon_pack)
    return _Setup(
        mode=mode,
        editors=tuple(editors),
        client=client,
        workers=workers,
        runner=runner,
        budget=budget,
        story=story,
        names=list(names),
        changes=changes,
        dismissals=dismissals,
        commit_sha=commit_sha,
        slices=slices,
        canon_block=canon_block,
    )


def _estimate(
    setup: _Setup, plans: Mapping[str, tuple[str | None, Sequence[ReviewUnit]]]
) -> CostEstimate:
    """Price one worst-case call per unit that will be sent (see :class:`CostEstimate`)."""
    usage = setup.client.usage_summary()
    model = str(usage["model"])
    rate, priced = cap_rate(model, str(usage["profile"]))
    calls = prompt_tokens = completion_tokens = 0
    for name, (_skip, units) in plans.items():
        prompt_name, max_tokens = _EDITOR_REQUESTS[name]
        schema = prompt_schema(prompt_name)
        allowance = max(max_tokens, REASONING_MIN_MAX_TOKENS)
        for unit in units:
            if unit.over_budget:
                continue
            prompt = _EDITOR_PROMPTS[name](setup.story, unit, setup.canon_for(name, unit))
            calls += 1
            prompt_tokens += prompt_token_bound(prompt.system, prompt.user, schema)
            completion_tokens += allowance
    return CostEstimate(
        calls=calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        usd=cap_usd(rate, prompt_tokens, completion_tokens),
        priced=priced,
        model=model,
    )


def _refusal(client: Completer, estimate_usd: float) -> str | None:
    """Return why the run may not start (monthly cap, spend ledger), or ``None``."""
    try:
        client.check_spend(estimate_usd)
    except LLMRunHalted as exc:
        return exc.reason
    return None


def _artifact(
    setup: _Setup, entries: list[dict[str, Any]], now: datetime | None
) -> dict[str, Any]:
    stamp = (now or datetime.now(UTC)).astimezone(UTC)
    artifact = {
        "version": ARTIFACT_VERSION,
        "generated_at": stamp.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "commit_sha": setup.commit_sha,
        "base_sha": setup.changes["base_sha"] if setup.changes is not None else None,
        "mode": setup.mode,
        "llm": {**setup.client.usage_summary(), "runner": setup.runner},
        "editors": entries,
    }
    if setup.canon_block is not None:
        artifact["canon"] = setup.canon_block
    validate_artifact(artifact, "ai_review")
    return artifact


def _not_started(setup: _Setup, reason: str, now: datetime | None) -> dict[str, Any]:
    entries = [
        _editor_entry(name, reason, [], [], setup.dismissals, setup.intentional)
        for name in setup.editors
    ]
    return _artifact(setup, entries, now)


def estimate_review(
    repo: Path,
    mode: str,
    passage: str | None = None,
    editors: Sequence[str] = EDITORS,
    client: Completer | None = None,
    *,
    env: Mapping[str, str] | None = None,
    canon_path: Path | None = None,
) -> CostEstimate:
    """Work out what a review would cost at most, calling no model.

    Args:
        repo: Repository root, built as for :func:`review`.
        mode: ``changed``, ``all`` or ``passage``.
        passage: The passage for mode ``passage``.
        editors: Editors to count.
        client: The completer whose model and profile set the rate; defaults to
            ``LLMClient(Settings.from_env())``.
        env: Environment for the runner, unit budget and LLM settings.
        canon_path: The canon pack; defaults to ``<repo>/dist/canon-pack.json``.

    Returns:
        The estimate.

    Raises:
        ReviewConfigError: Bad mode, passage, editor list, runner or budget.
        LLMConfigError: No client given and the LLM settings are unusable.
        BuildError: A required build artifact (including the canon pack) is missing.
        ArtifactValidationError: The canon pack does not match its schema.
        GitError: The repository has no ``HEAD`` commit.
    """
    setup = _setup(repo, mode, passage, editors, client, None, env, None, canon_path)
    return _estimate(setup, setup.plans())


def preflight(
    repo: Path,
    mode: str,
    passage: str | None = None,
    editors: Sequence[str] = EDITORS,
    client: Completer | None = None,
    dismissals_path: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
    canon_path: Path | None = None,
) -> tuple[CostEstimate, dict[str, Any] | None]:
    """Estimate a review and check that the monthly cap has room for it, calling no model.

    ``/check-continuity all`` runs this before it says the review is running
    (AC-continuity-review-11), and starts nothing when the estimate does not fit
    (AC-continuity-review-35).

    Args:
        repo: Repository root, built as for :func:`review`.
        mode: ``changed``, ``all`` or ``passage``.
        passage: The passage for mode ``passage``.
        editors: Editors to run.
        client: The completer; defaults to ``LLMClient(Settings.from_env())``.
        dismissals_path: Defaults to ``<repo>/ai/dismissals.jsonl``.
        env: Environment for the runner, unit budget and LLM settings.
        now: Timestamp for ``generated_at`` of a refusal.
        canon_path: The canon pack; defaults to ``<repo>/dist/canon-pack.json``.

    Returns:
        ``(estimate, None)`` when the review may start, or ``(estimate, artifact)`` when
        it may not: the ``ai_review`` artifact with every editor ``skipped`` with the
        reason (the monthly cap, or an unreadable spend ledger), as :func:`review` writes
        it when it stops before its first call.

    Raises:
        ReviewConfigError: Bad mode, passage, editor list, runner, budget, or dismissals.
        LLMConfigError: No client given and the LLM settings are unusable.
        BuildError: A required build artifact (including the canon pack) is missing.
        ArtifactValidationError: The canon pack does not match its schema.
        GitError: The repository has no ``HEAD`` commit.
    """
    setup = _setup(repo, mode, passage, editors, client, dismissals_path, env, None, canon_path)
    estimate = _estimate(setup, setup.plans())
    reason = _refusal(setup.client, estimate.usd)
    return estimate, None if reason is None else _not_started(setup, reason, now)


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
    canon_path: Path | None = None,
) -> dict[str, Any]:
    """Run the editors and return the ``ai_review`` artifact.

    Before any call, mode ``all`` checks that the monthly cap has room for its whole
    :class:`CostEstimate`; the other modes check only that the cap is not reached.

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
        canon_path: The canon pack; defaults to ``<repo>/dist/canon-pack.json``. Read only
            when the Continuity Editor runs.

    Returns:
        The artifact, validated against ``ai_review``.

    Raises:
        ReviewConfigError: Bad mode, passage, editor list, runner, budget, or dismissals.
        LLMConfigError: No client given and the LLM settings are unusable.
        BuildError: A required build artifact (including the canon pack) is missing.
        ArtifactValidationError: The canon pack does not match its schema.
        GitError: The repository has no ``HEAD`` commit.
    """
    setup = _setup(
        repo, mode, passage, editors, client, dismissals_path, env, max_workers, canon_path
    )
    client = setup.client
    plans = setup.plans()
    needed = _estimate(setup, plans).usd if mode == "all" else 0.0
    reason = _refusal(client, needed)
    if reason is not None:
        return _not_started(setup, reason, now)

    jobs = [(name, unit) for name in setup.editors for unit in plans[name][1]]
    halt = _Halt()
    with ThreadPoolExecutor(max_workers=max(1, setup.workers)) as pool:
        futures = [
            pool.submit(
                _run_unit, client, setup.story, name, unit, halt, setup.canon_for(name, unit)
            )
            for name, unit in jobs
        ]
        outcomes = [future.result() for future in futures]

    entries = []
    cursor = 0
    intentional = setup.intentional
    for name in setup.editors:
        skip_reason, units = plans[name]
        mine = outcomes[cursor : cursor + len(units)]
        cursor += len(units)
        entries.append(
            _editor_entry(name, skip_reason, units, mine, setup.dismissals, intentional)
        )
    return _artifact(setup, entries, now)


def _canon(
    paths: ProjectPaths, story: ReviewStory, names: Sequence[str], pack_path: Path
) -> tuple[dict[str, CanonSlice], dict[str, Any]]:
    """Load the canon pack and select each reviewed passage's slice.

    Current hashes come from ``src/`` through the bible's own reader, so a passage counts
    as read by the Bible exactly when the extraction would skip it.
    """
    pack = load_canon_pack(pack_path)
    if paths.src.is_dir():
        current = {p.name: p.content_hash for p in bible_passages(paths.repo, paths.src)}
    else:
        current = {name: story.hash(name) for name in story.content}
    slices = {name: select_canon(pack, name, story.content[name], current) for name in names}
    source = pack["source"]
    block = {
        "status": "used" if source["cache_present"] else "no_cache",
        "extracted_at": source["extracted_at"],
        "commit": source["commit"],
        "facts_offered": sum(len(piece.facts) for piece in slices.values()),
        "stale_excluded": sum(piece.stale_excluded for piece in slices.values()),
        "passages_not_in_bible": sorted(
            name for name in names if pack["passages"].get(name) != current.get(name)
        )
        if source["cache_present"]
        else [],
    }
    return slices, block


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
