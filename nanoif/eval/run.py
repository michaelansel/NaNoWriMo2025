"""``nanoif ai eval``: review the eval story and score the editors against ``truth.json``.

The fixture is copied into a scratch directory, committed on top of an empty base commit
(so every passage is ``changed``), built into ``story_graph.json`` and ``changes.json``
from raw Twee (no Tweego needed), and reviewed in mode ``all``. Extraction metrics belong
to the Story Bible, which arrives in Phase 3: they are marked skipped, never scored as zero.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nanoif.build.paths import ProjectPaths
from nanoif.errors import BuildError
from nanoif.eval.report import diff_against_baseline, render_markdown
from nanoif.eval.score import run_scoring
from nanoif.formats.allpaths import AllPathsConfig, run
from nanoif.git.service import snapshot_repository
from nanoif.llm.client import Completer
from nanoif.review.runner import review
from nanoif.schemas.artifacts import write_artifact
from nanoif.twee.parse import parse_twee_dir

EXTRACTION_SKIPPED = "bible: not implemented until Phase 3"
EXTRACTION_SECTIONS = ("entities", "facts", "pronouns")
EXTRACTION_METRICS = (
    "entity_recall",
    "entity_precision",
    "distractor_hits",
    "fact_recall",
    "fact_precision",
    "scene_state_leaks",
    "pronoun_accuracy",
)


@dataclass(frozen=True)
class EvalOutcome:
    """What an eval run produced.

    Attributes:
        scores: Scores with extraction sections marked skipped and a ``review`` block.
        review: The ``ai_review`` artifact of the run.
        diff: Baseline comparison, when a baseline was given.
        markdown: The report.
    """

    scores: dict[str, Any]
    review: dict[str, Any]
    diff: dict[str, Any] | None
    markdown: str

    @property
    def review_ok(self) -> bool:
        """Whether every editor reviewed every unit."""
        return all(editor["status"] == "ok" for editor in self.review["editors"])

    @property
    def ok(self) -> bool:
        """Review complete and no metric below the baseline."""
        return self.review_ok and (self.diff is None or self.diff["ok"])


def prepare_eval_repo(fixture: Path, workdir: Path) -> ProjectPaths:
    """Copy a fixture story into ``workdir``, commit it on an empty base, and build it.

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
    return paths


def results_from_review(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Convert an ``ai_review`` artifact into the results shape ``run_scoring`` expects.

    Only reader-facing findings count; unverified and suppressed findings do not.

    Args:
        artifact: The review artifact.

    Returns:
        ``{"findings", "conflicts", "usage"}``.
    """
    findings: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for editor in artifact["editors"]:
        for finding in editor["findings"]:
            names = [ref["name"] for ref in finding["passages"]]
            findings.append(
                {"type": finding["type"], "passages": names, "severity": finding["severity"]}
            )
            if editor["name"] == "continuity":
                conflicts.append({"passages": names, "intentional": False})
    return {"findings": findings, "conflicts": conflicts, "usage": artifact["llm"]}


def mark_extraction_skipped(scores: dict[str, Any]) -> dict[str, Any]:
    """Replace extraction sections and metrics with an explicit skipped marker.

    Args:
        scores: Output of :func:`nanoif.eval.score.run_scoring`.

    Returns:
        The same scores with ``entities``/``facts``/``pronouns`` set to
        ``{"skipped": EXTRACTION_SKIPPED}``, their metrics removed, and
        ``skipped_metrics`` naming each removed metric with the reason.
    """
    for section in EXTRACTION_SECTIONS:
        scores[section] = {"skipped": EXTRACTION_SKIPPED}
    for metric in EXTRACTION_METRICS:
        scores["metrics"].pop(metric, None)
    scores["skipped_metrics"] = {metric: EXTRACTION_SKIPPED for metric in EXTRACTION_METRICS}
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


def run_eval(
    fixture: Path,
    client: Completer,
    workdir: Path,
    baseline: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> EvalOutcome:
    """Review the eval story with ``client`` and score the result.

    Args:
        fixture: The eval story directory (``src/``, ``truth.json``).
        client: The completer to evaluate.
        workdir: Scratch directory to build the story in.
        baseline: Parsed baseline JSON to diff against, if any.
        env: Environment for the review (runner, unit budget); defaults to ``os.environ``.

    Returns:
        Scores, the review artifact, the baseline diff, and the Markdown report.

    Raises:
        BuildError: The fixture is incomplete.
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
    artifact = review(
        paths.repo,
        "all",
        client=client,
        dismissals_path=paths.repo / "ai" / "dismissals.jsonl",
        env=env,
    )
    scores = mark_extraction_skipped(run_scoring(truth, results_from_review(artifact)))
    scores["review"] = review_summary(artifact)
    diff = diff_against_baseline(scores, baseline) if baseline is not None else None
    return EvalOutcome(scores, artifact, diff, render_markdown(scores, baseline))
