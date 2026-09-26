"""``nanoif ai eval``: extract the eval story's Story Bible, review it, score both.

The fixture (``src/`` and ``story-overrides.txt``) is copied into a scratch directory,
committed on top of an empty base commit (so every passage is ``changed``) and built into
``story_graph.json`` and ``changes.json`` from raw Twee (no Tweego needed). Then
(ADR-020):

1. ``nanoif bible extract --full`` runs on the scratch repository;
2. the canon pack is built from the resulting cache and the fixture overrides;
3. both editors review every passage (mode ``all``) with that canon;
4. ``entities``, ``facts``, ``pronouns`` (from references) and ``conflicts`` (bible
   conflicts) are scored from the Bible; conflicts the Continuity Editor reports are scored
   separately as ``review_conflicts``.

An extraction halt (spend cap, token budget, ledger) marks the bible sections skipped with
the reason, and the eval is not ``ok``; so is a partial extraction.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nanoif.bible.assemble import Bible, load_bible
from nanoif.bible.cache import BibleCache, load_cache
from nanoif.bible.canon import write_canon_pack
from nanoif.bible.run import extract_bible
from nanoif.build.paths import ProjectPaths
from nanoif.errors import BuildError
from nanoif.eval.report import diff_against_baseline, render_markdown
from nanoif.eval.score import run_scoring
from nanoif.formats.allpaths import AllPathsConfig, run
from nanoif.git.service import snapshot_repository
from nanoif.llm.client import Completer
from nanoif.llm.errors import LLMRunHalted
from nanoif.llm.ledger import spend_line
from nanoif.review.runner import review
from nanoif.schemas.artifacts import write_artifact
from nanoif.twee.parse import parse_twee_dir

EXTRACTION_SECTIONS = ("entities", "facts", "pronouns", "conflicts")
EXTRACTION_METRICS = (
    "entity_recall",
    "entity_precision",
    "distractor_hits",
    "fact_recall",
    "fact_precision",
    "scene_state_leaks",
    "pronoun_accuracy",
    "conflict_recall",
    "conflict_precision",
    "intentional_flagged",
)


@dataclass(frozen=True)
class EvalOutcome:
    """What an eval run produced.

    Attributes:
        scores: Scores, with a ``review`` and an ``extraction`` block.
        review: The ``ai_review`` artifact of the run.
        diff: Baseline comparison, when a baseline was given.
        markdown: The report.
        extraction: ``{status, reason, summary}``: ``ok``, ``partial`` or ``halted``.
    """

    scores: dict[str, Any]
    review: dict[str, Any]
    diff: dict[str, Any] | None
    markdown: str
    extraction: dict[str, Any]

    @property
    def review_ok(self) -> bool:
        """Whether every editor reviewed every unit."""
        return all(editor["status"] == "ok" for editor in self.review["editors"])

    @property
    def extraction_ok(self) -> bool:
        """Whether the extraction read every passage and reconciled every entity."""
        return self.extraction["status"] == "ok"

    @property
    def ok(self) -> bool:
        """Extraction and review complete, and no metric below the baseline."""
        return (
            self.review_ok and self.extraction_ok and (self.diff is None or self.diff["ok"])
        )


def prepare_eval_repo(fixture: Path, workdir: Path) -> ProjectPaths:
    """Copy a fixture story into ``workdir``, commit it on an empty base, and build it.

    The canon pack is built too, from no saved extraction (review with earlier passages
    only), as ``nanoif build all`` would.

    Args:
        fixture: Directory with ``src/`` (and optionally ``story-overrides.txt``).
        workdir: An empty or missing directory to build in.

    Returns:
        The layout of the built repository.

    Raises:
        BuildError: The fixture has no ``src/``.
        GitError: A git command failed.
        StoryParseError: The fixture story does not parse.
    """
    source = fixture / "src"
    if not source.is_dir():
        raise BuildError(f"eval fixture has no src/: {fixture}")
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, workdir / "src")
    overrides = fixture / "story-overrides.txt"
    if overrides.is_file():
        shutil.copy2(overrides, workdir / "story-overrides.txt")
    base_sha, _head = snapshot_repository(workdir, "eval story")
    paths = ProjectPaths.from_repo(workdir)
    write_artifact(paths.story_graph, parse_twee_dir(paths.src), "story_graph")
    run(
        AllPathsConfig(
            repo_root=workdir,
            src_dir=paths.src,
            story_graph_path=paths.story_graph,
            output_dir=paths.dist,
            base_ref=base_sha,
        )
    )
    write_canon_pack(load_bible(workdir, paths.cache), paths.canon_pack)
    return paths


def results_from_bible(bible: Bible, cache: BibleCache | None) -> dict[str, Any]:
    """Convert the assembled Bible into the results shape ``run_scoring`` expects.

    Pinned facts come from ``story-overrides.txt``, not extraction, so they are not scored.

    Args:
        bible: The Bible assembled from the eval extraction and the fixture overrides.
        cache: The cache, for pronoun references.

    Returns:
        ``{"entities", "facts", "pronouns", "conflicts"}``.
    """
    entities = [
        {"name": e.name, "type": e.type, "aliases": list(e.aliases)}
        for e in bible.entities
        if e.type != "world"
    ]
    facts = [
        {"entity": e.name, "claim": f.claim, "passage": f.passage, "evidence_phrase": f.quote}
        for e in bible.entities
        for f in (*e.facts, *e.rules)
        if not f.pinned
    ]
    names = {e.slug: e.name for e in bible.entities}
    if cache is not None:
        for slug, entity in cache.entities.items():
            names.setdefault(slug, entity.name)
    pronouns = [
        {"passage": passage, "sentence": ref.quote, "entity": names.get(ref.entity or "")}
        for passage, record in sorted((cache.passages if cache else {}).items())
        for ref in record.references
    ]
    conflicts = [
        {"id": c.id, "passages": [f.passage for f in c.facts], "intentional": False}
        for c in bible.conflicts
    ] + [
        {"id": c.id, "passages": [f.passage for f in c.facts], "intentional": True}
        for mystery in bible.mysteries
        for c in mystery.conflicts
    ]
    return {"entities": entities, "facts": facts, "pronouns": pronouns, "conflicts": conflicts}


def results_from_review(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Convert an ``ai_review`` artifact into findings and review-derived conflicts.

    Only reader-facing findings count; unverified and suppressed findings do not.

    Args:
        artifact: The review artifact.

    Returns:
        ``{"findings", "review_conflicts", "usage"}``.
    """
    findings: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for editor in artifact["editors"]:
        for finding in editor["findings"]:
            names = [ref["name"] for ref in finding["passages"]]
            findings.append(
                {
                    "type": finding["type"],
                    "passages": names,
                    "severity": finding["severity"],
                    "editor": editor["name"],
                    "key": finding.get("key"),
                    "description": finding.get("description", ""),
                }
            )
            if editor["name"] == "continuity":
                conflicts.append({"passages": names, "intentional": False})
    return {"findings": findings, "review_conflicts": conflicts, "usage": artifact["llm"]}


def mark_extraction_skipped(scores: dict[str, Any], reason: str) -> dict[str, Any]:
    """Replace the bible sections and metrics with an explicit skipped marker.

    Args:
        scores: Output of :func:`nanoif.eval.score.run_scoring`.
        reason: Why extraction produced nothing to score.

    Returns:
        The same scores with each bible section set to ``{"skipped": reason}``, its
        metrics removed, and ``skipped_metrics`` naming each removed metric with the reason.
    """
    for section in EXTRACTION_SECTIONS:
        scores[section] = {"skipped": reason}
    for metric in EXTRACTION_METRICS:
        scores["metrics"].pop(metric, None)
    scores["skipped_metrics"] = {metric: reason for metric in EXTRACTION_METRICS}
    return scores


def review_summary(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize each editor's coverage for the eval report.

    Args:
        artifact: The review artifact.

    Returns:
        ``{"editors": [{name, status, reason, units, reviewed, findings, unverified}]}``.
    """
    return {
        "editors": [
            {
                "name": editor["name"],
                "status": editor["status"],
                "reason": editor["reason"],
                "units": len(editor["units"]),
                "reviewed": sum(1 for unit in editor["units"] if unit["status"] == "reviewed"),
                "findings": len(editor["findings"]),
                "unverified": len(editor["unverified"]),
            }
            for editor in artifact["editors"]
        ]
    }


def _extract(paths: ProjectPaths, client: Completer) -> dict[str, Any]:
    try:
        outcome = extract_bible(
            paths.repo, "full", client, paths.cache, False, diff_out=paths.bible_diff
        )
    except LLMRunHalted as exc:
        return {"status": "halted", "reason": f"extraction halted: {exc.reason}", "summary": None}
    reason = None
    if outcome.status == "partial":
        failed = len(outcome.diff["passages_failed"])
        pending = len(outcome.diff["pending"])
        reason = f"{failed} passage(s) not read, {pending} entity(ies) pending"
    return {"status": outcome.status, "reason": reason, "summary": outcome.summary}


def run_eval(
    fixture: Path,
    client: Completer,
    workdir: Path,
    baseline: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> EvalOutcome:
    """Extract, review and score the eval story with ``client``.

    Args:
        fixture: The eval story directory (``src/``, ``story-overrides.txt``, ``truth.json``).
        client: The completer to evaluate.
        workdir: Scratch directory to build the story in.
        baseline: Parsed baseline JSON to diff against, if any.
        env: Environment for the review (runner, unit budget); defaults to ``os.environ``.

    Returns:
        Scores, the review artifact, the baseline diff, the report and the extraction status.

    Raises:
        BuildError: The fixture is incomplete.
        BibleError: The scratch repository has no story source.
        GitError: The scratch repository could not be created.
        ReviewConfigError: The review could not start.
    """
    truth_path = fixture / "truth.json"
    if not truth_path.is_file():
        raise BuildError(f"eval fixture has no truth.json: {fixture}")
    try:
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"{truth_path} is not valid JSON: {exc}") from exc
    paths = prepare_eval_repo(fixture, workdir)
    extraction = _extract(paths, client)
    bible = load_bible(paths.repo, paths.cache)
    write_canon_pack(bible, paths.canon_pack)
    artifact = review(
        paths.repo,
        "all",
        client=client,
        dismissals_path=paths.repo / "ai" / "dismissals.jsonl",
        env=env,
    )
    results = {**results_from_bible(bible, load_cache(paths.cache)),
               **results_from_review(artifact)}
    scores = run_scoring(truth, results)
    if extraction["status"] == "halted":
        scores = mark_extraction_skipped(scores, extraction["reason"])
    scores["extraction"] = extraction
    scores["review"] = review_summary(artifact)
    diff = diff_against_baseline(scores, baseline) if baseline is not None else None
    if spend := spend_line(artifact["llm"]):
        scores["spend"] = spend
    return EvalOutcome(scores, artifact, diff, render_markdown(scores, baseline), extraction)
