"""Render eval scores as Markdown or JSON and diff them against a committed baseline.

A baseline file (``tests/eval/baselines/<profile>.json``) is either a flat
``{metric: value}`` mapping or ``{"profile": ..., "metrics": {metric: value}}``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

HIGHER_IS_BETTER = (
    "entity_recall",
    "entity_precision",
    "fact_recall",
    "fact_precision",
    "conflict_recall",
    "conflict_precision",
    "intentional_flagged",
    "defects_detected",
    "defect_severity_matches",
    "pronoun_accuracy",
)
LOWER_IS_BETTER = (
    "distractor_hits",
    "scene_state_leaks",
    "clean_path_false_positives",
    "intentional_leaks",
    "total_tokens",
    "usd",
)
# Cost metrics may drift run to run; only a rise past this fraction is a regression.
COST_METRICS = frozenset({"total_tokens", "usd"})
COST_TOLERANCE = 0.25

_LABELS = {
    "entity_recall": "Entity recall",
    "entity_precision": "Entity precision",
    "distractor_hits": "Distractor entities",
    "fact_recall": "Fact recall",
    "fact_precision": "Fact precision",
    "scene_state_leaks": "Scene-state facts",
    "conflict_recall": "Conflict recall",
    "conflict_precision": "Conflict precision",
    "intentional_flagged": "Intentional conflict flagged",
    "defects_detected": "Defects detected",
    "defect_severity_matches": "Defect severities right",
    "pronoun_accuracy": "Pronoun accuracy",
    "clean_path_false_positives": "Clean-path false positives",
    "intentional_leaks": "Intentional-conflict leaks",
    "total_tokens": "Tokens",
    "usd": "USD",
}


def baseline_metrics(baseline: Mapping[str, Any]) -> dict[str, float]:
    """Return the flat metric mapping from either baseline file shape.

    Args:
        baseline: Parsed baseline JSON.

    Returns:
        ``{metric: value}`` with numeric values only.
    """
    source = baseline.get("metrics", baseline)
    return {
        k: v for k, v in source.items() if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def diff_against_baseline(scores: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    """Flag every metric that moved the wrong way from the baseline.

    Args:
        scores: Output of :func:`nanoif.eval.score.run_scoring` (or its ``metrics`` dict).
        baseline: Parsed baseline JSON.

    Returns:
        ``ok`` (no regressions), ``regressions``, ``improvements``, ``unchanged`` (each a
        list of ``{metric, baseline, current}``), and ``missing`` metrics the baseline has
        but the scores lack. Metrics the scores list under ``skipped_metrics`` (a section
        that was not run, with its reason) go to ``skipped`` instead and do not fail ``ok``.
    """
    current = dict(scores.get("metrics", scores))
    skipped_reasons = scores.get("skipped_metrics", {}) if "metrics" in scores else {}
    base = baseline_metrics(baseline)
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    missing: list[str] = []
    skipped: list[str] = []
    for metric, previous in base.items():
        if metric not in current:
            (skipped if metric in skipped_reasons else missing).append(metric)
            continue
        value = current[metric]
        row = {"metric": metric, "baseline": previous, "current": value}
        if metric in LOWER_IS_BETTER:
            limit = previous * (1 + COST_TOLERANCE) if metric in COST_METRICS else previous
            if value > limit:
                regressions.append(row)
            elif value < previous:
                improvements.append(row)
            else:
                unchanged.append(row)
        else:
            if value < previous:
                regressions.append(row)
            elif value > previous:
                improvements.append(row)
            else:
                unchanged.append(row)
    return {
        "ok": not regressions and not missing,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "missing": missing,
        "skipped": skipped,
    }


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


def render_markdown(scores: Mapping[str, Any], baseline: Mapping[str, Any] | None = None) -> str:
    """Render the metrics table, with a baseline column and flags when a baseline is given.

    Args:
        scores: Output of :func:`nanoif.eval.score.run_scoring`.
        baseline: Parsed baseline JSON, or ``None``.

    Returns:
        Markdown text.
    """
    metrics = scores["metrics"]
    totals = scores.get("totals", {})
    diff = diff_against_baseline(scores, baseline) if baseline is not None else None
    flags: dict[str, str] = {}
    if diff is not None:
        flags.update({r["metric"]: "regression" for r in diff["regressions"]})
        flags.update({r["metric"]: "improved" for r in diff["improvements"]})
    base = baseline_metrics(baseline) if baseline is not None else {}

    lines = ["| Metric | Value |" + (" Baseline | Change |" if baseline is not None else "")]
    lines.append("|---|---|" + ("---|---|" if baseline is not None else ""))
    for metric in (*HIGHER_IS_BETTER, *LOWER_IS_BETTER):
        if metric not in metrics:
            continue
        row = f"| {_LABELS.get(metric, metric)} | {_fmt(metrics[metric])} |"
        if baseline is not None:
            previous = base.get(metric)
            row += f" {_fmt(previous) if previous is not None else '-'} | {flags.get(metric, '')} |"
        lines.append(row)

    entities, facts = scores["entities"], scores["facts"]
    detail = [
        f"Entities: skipped ({entities['skipped']})."
        if "skipped" in entities
        else f"Entities: {entities['recall']:.0%} recall, "
        f"missed {', '.join(entities['missed']) or 'none'}; "
        f"spurious {', '.join(entities['spurious']) or 'none'}.",
        f"Facts: skipped ({facts['skipped']})."
        if "skipped" in facts
        else f"Facts: {len(facts['recalled'])}/{facts['expected']} recalled; "
        f"missed {', '.join(facts['missed']) or 'none'}.",
        f"Conflicts: found {', '.join(scores['conflicts']['found']) or 'none'}; "
        f"missed {', '.join(scores['conflicts']['missed']) or 'none'}.",
        "Defects: "
        + ", ".join(
            f"{row['id']} {'found' if row['detected'] else 'missed'}"
            for row in scores["defects"]["per_defect"]
        ),
        f"Cost: {totals.get('calls', 0)} calls, {totals.get('total_tokens', 0)} tokens, "
        f"${totals.get('usd', 0.0):.4f}"
        + ("" if totals.get("usd_known") else " (rate unknown)")
        + f" on {totals.get('profile') or '?'} ({totals.get('model') or '?'}).",
    ]
    pronouns = scores.get("pronouns", {})
    if "skipped" in pronouns:
        detail.append(f"Pronouns: skipped ({pronouns['skipped']}).")
    elif not pronouns.get("scored", False):
        detail.append("Pronouns: not scored (no resolutions reported).")
    for editor in scores.get("review", {}).get("editors", []):
        line = (
            f"Review {editor['name']}: {editor['status']}, {editor['reviewed']} of "
            f"{editor['units']} units reviewed, {editor['findings']} finding(s), "
            f"{editor['unverified']} unverified"
        )
        if editor.get("reason"):
            line += f" ({editor['reason']})"
        detail.append(line + ".")
    if scores.get("skipped_metrics"):
        reasons = sorted(set(scores["skipped_metrics"].values()))
        detail.append(
            f"Skipped metrics: {', '.join(scores['skipped_metrics'])} ({'; '.join(reasons)})."
        )
    if diff is not None:
        if diff["ok"]:
            detail.append("Baseline: no metric below baseline.")
        else:
            names = [r["metric"] for r in diff["regressions"]] + [
                f"{m} (missing)" for m in diff["missing"]
            ]
            detail.append("Baseline: regressions in " + ", ".join(names) + ".")
    return "\n".join(lines) + "\n\n" + "\n".join(f"- {line}" for line in detail) + "\n"


def to_json(scores: Mapping[str, Any]) -> str:
    """Serialize scores deterministically.

    Args:
        scores: Output of :func:`nanoif.eval.score.run_scoring`.

    Returns:
        Indented JSON with sorted keys and a trailing newline.
    """
    return json.dumps(scores, indent=2, sort_keys=True) + "\n"
