"""Render sticky comments and check-run payloads from the workflow's JSON artifacts.

Inputs are ``ai-review.json`` (schema ``ai_review``) for the Continuity and Style
editors and ``nanoif check structure --format json`` plus ``dist/`` for the Build &
Structure comment. Every model- or story-derived string goes through
:func:`nanoif.github.sanitize.sanitize` here, before it reaches a template; the
templates never see raw text.

Honesty rules the rendering enforces:

* "No findings" appears only for an editor whose status is ``ok`` with zero findings.
* An editor with status ``error`` or ``skipped`` opens with "unavailable" or
  "partially unavailable", names the reason, lists every passage it could not check,
  and its check run concludes ``failure``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from nanoif.github.comments import MARKER_BUILD, MARKER_CONTINUITY, MARKER_STYLE
from nanoif.github.sanitize import sanitize
from nanoif.schemas.artifacts import load_artifact

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "github"
SEVERITIES = ("critical", "major", "minor")
MAX_LISTED = 25
QUOTE_CHARS = 300
RETRY = "/check-continuity"

# Output files the Build comment reports, in display order.
BUILD_OUTPUTS = (
    ("Playable story", "play.html"),
    ("Proofread", "proofread.html"),
    ("Story map", "graph.html"),
    ("All paths", "allpaths.html"),
    ("Writing metrics", "metrics.html"),
    ("Story Bible", "story-bible.html"),
    ("Passage index", "passages.html"),
)
STRUCTURE_CHECK = "Structure"
_ANNOTATION_LEVEL = {"error": "failure", "warning": "warning", "info": "notice"}


@dataclass(frozen=True)
class EditorSpec:
    """Display name, sticky marker and check-run name of one editor."""

    name: str
    title: str
    marker: str


EDITORS = {
    "continuity": EditorSpec("continuity", "Continuity Editor", MARKER_CONTINUITY),
    "style": EditorSpec("style", "Style Editor", MARKER_STYLE),
}


@dataclass(frozen=True)
class RunInfo:
    """The workflow run a report belongs to."""

    run_id: str | None = None
    url: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> RunInfo:
        """Read ``GITHUB_RUN_ID``, ``GITHUB_SERVER_URL`` and ``GITHUB_REPOSITORY``."""
        env = os.environ if env is None else env
        run_id = env.get("GITHUB_RUN_ID") or None
        server = env.get("GITHUB_SERVER_URL") or "https://github.com"
        repo = env.get("GITHUB_REPOSITORY")
        url = f"{server}/{repo}/actions/runs/{run_id}" if run_id and repo else None
        return cls(run_id, url)

    @property
    def label(self) -> str:
        """``[run #N](url)``, ``run #N``, or ``local run``."""
        if self.run_id and self.url:
            return f"[run #{self.run_id}]({self.url})"
        return f"run #{self.run_id}" if self.run_id else "local run"


@dataclass(frozen=True)
class CheckPayload:
    """Everything :meth:`GitHubAPI.create_check_run` needs besides the head SHA."""

    name: str
    conclusion: str
    title: str
    summary: str
    text: str = ""
    annotations: tuple[dict[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Rendered:
    """A sticky comment body and the matching check run."""

    marker: str
    body: str
    check: CheckPayload


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,  # Markdown; untrusted text is sanitized before rendering
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _plural(count: int, word: str, plural: str | None = None) -> str:
    return f"{count} {word if count == 1 else (plural or word + 's')}"


# -- AI editors ------------------------------------------------------------------------


def editor_conclusion(editor: Mapping[str, Any]) -> str:
    """Map an editor result to a check-run conclusion.

    Args:
        editor: One entry of ``ai-review.json`` ``editors``.

    Returns:
        ``success`` for ok with no findings, ``neutral`` for ok with findings,
        ``failure`` for ``error`` or ``skipped``.
    """
    if editor["status"] != "ok":
        return "failure"
    return "neutral" if editor["findings"] else "success"


def _cost(llm: Mapping[str, Any]) -> str:
    if not llm.get("usd_known"):
        return "cost unknown"
    return f"≈ ${llm['usd']:.4f}" if llm["usd"] < 0.01 else f"≈ ${llm['usd']:.2f}"


def header_line(review: Mapping[str, Any], editor: Mapping[str, Any], run: RunInfo) -> str:
    """Return the cost header (Contract F) for one editor.

    ``Continuity Editor · N passages reviewed · X findings, Y suppressed · in/out tokens ·
    ≈ $cost · <profile> (<model>) · run #<id>``. Token and cost figures cover the whole
    review run (both editors), as ``LLMClient.usage_summary()`` reports them.
    """
    llm = review["llm"]
    reviewed = sum(1 for unit in editor["units"] if unit["status"] == "reviewed")
    parts = [
        EDITORS[editor["name"]].title,
        f"{_plural(reviewed, 'passage')} reviewed",
        f"{_plural(len(editor['findings']), 'finding')}, {len(editor['suppressed'])} suppressed",
        f"{llm['prompt_tokens']:,} in / {llm['completion_tokens']:,} out tokens",
        _cost(llm),
        f"{sanitize(llm['profile'], 60)} ({sanitize(llm['model'], 120)})",
        run.label,
    ]
    return " · ".join(parts)


def _unit_reason(editor: Mapping[str, Any]) -> str:
    if editor.get("reason"):
        return sanitize(editor["reason"], 300)
    for unit in editor["units"]:
        if unit["status"] != "reviewed" and unit.get("reason"):
            return sanitize(unit["reason"], 300)
    return "no reason recorded"


def _status(editor: Mapping[str, Any], mode: str) -> tuple[str, str]:
    """Return (headline, lead paragraph) for an editor."""
    title = EDITORS[editor["name"]].title
    units = editor["units"]
    failed = [unit for unit in units if unit["status"] != "reviewed"]
    reason = _unit_reason(editor)
    if editor["status"] == "skipped":
        return (
            "unavailable",
            f"The {title} did not run: {reason}. Nothing was checked, so this is not a "
            f"pass. Retry with `{RETRY}`.",
        )
    if editor["status"] == "error":
        if len(failed) < len(units):
            return (
                "partially unavailable",
                f"{len(failed)} of {_plural(len(units), 'passage')} could not be checked "
                f"({reason}). Findings below cover only the passages that were reviewed. "
                f"Retry with `{RETRY}`.",
            )
        return (
            "unavailable",
            f"No passage could be checked: {reason}. Nothing was checked, so this is not "
            f"a pass. Retry with `{RETRY}`.",
        )
    count = len(editor["findings"])
    if count:
        return _plural(count, "finding"), ""
    if not units:
        return "No findings", "No story passages changed, so there was nothing to review."
    scope = "every passage" if mode == "all" else _plural(len(units), "passage")
    return "No findings", f"Reviewed {scope}; nothing needs a look."


def _finding_view(finding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "key": finding["key"],
        "type": sanitize(finding["type"], 60),
        "severity": finding["severity"],
        "confidence": finding["confidence"],
        "description": sanitize(finding["description"], 500),
        "passages": [sanitize(p["name"], 200) for p in finding["passages"]],
        "quotes": [
            {"text": sanitize(q["text"], QUOTE_CHARS), "passage": sanitize(q["passage"], 200)}
            for q in finding["quotes"]
        ],
        "routes_seen": finding.get("routes_seen") or 1,
    }


def _capped(findings: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    views = [_finding_view(f) for f in findings[:MAX_LISTED]]
    return views, max(0, len(findings) - MAX_LISTED)


def render_editor(review: Mapping[str, Any], editor_name: str, run: RunInfo) -> Rendered:
    """Render one editor's sticky comment and check run from ``ai-review.json``.

    Args:
        review: The validated ``ai-review.json`` document.
        editor_name: ``continuity`` or ``style``.
        run: The workflow run.

    Returns:
        The comment body (starting with the editor's marker) and check payload.

    Raises:
        KeyError: If the review has no such editor.
    """
    editor = next(e for e in review["editors"] if e["name"] == editor_name)
    spec = EDITORS[editor_name]
    headline, lead = _status(editor, review["mode"])
    groups = []
    for severity in SEVERITIES:
        matching = [f for f in editor["findings"] if f["severity"] == severity]
        if matching:
            views, overflow = _capped(matching)
            groups.append({"label": severity.capitalize(), "findings": views, "overflow": overflow})
    suppressed, suppressed_overflow = _capped(editor["suppressed"])
    unverified, unverified_overflow = _capped(editor["unverified"])
    not_checked = [
        {
            "passage": sanitize(unit["passage"], 200),
            "status": unit["status"],
            "reason": sanitize(unit.get("reason"), 300) or "no reason recorded",
        }
        for unit in editor["units"]
        if unit["status"] != "reviewed"
    ]
    header = header_line(review, editor, run)
    context = {
        "marker": spec.marker,
        "title": spec.title,
        "headline": headline,
        "header": header,
        "lead": lead,
        "groups": groups,
        "suppressed": suppressed,
        "suppressed_total": len(editor["suppressed"]),
        "suppressed_overflow": suppressed_overflow,
        "unverified": unverified,
        "unverified_total": len(editor["unverified"]),
        "unverified_overflow": unverified_overflow,
        "not_checked": not_checked,
        "retry": RETRY,
    }
    body = _environment().get_template("editor.md.jinja2").render(**context)
    check = CheckPayload(
        name=spec.title,
        conclusion=editor_conclusion(editor),
        title=f"{spec.title}: {headline}",
        summary=f"{header}\n\n{lead}".strip(),
        text=body.removeprefix(spec.marker).lstrip("\n"),
    )
    return Rendered(spec.marker, body, check)


def render_unavailable(editor_name: str, reason: str, run: RunInfo) -> Rendered:
    """Render the sticky comment and failed check run for an editor that could not run.

    Used when the ``exe`` runner is offline (there is no fallback provider) or the
    review crashed before writing ``ai-review.json``.

    Args:
        editor_name: ``continuity`` or ``style``.
        reason: Why it could not run (for example ``exe runner offline``).
        run: The workflow run.

    Returns:
        The comment body and a ``failure`` check payload.
    """
    spec = EDITORS[editor_name]
    context = {
        "marker": spec.marker,
        "title": spec.title,
        "reason": sanitize(reason, 300) or "no reason recorded",
        "run": run.label,
        "retry": RETRY,
    }
    body = _environment().get_template("unavailable.md.jinja2").render(**context)
    check = CheckPayload(
        name=spec.title,
        conclusion="failure",
        title=f"{spec.title} unavailable",
        summary=f"AI review unavailable: {context['reason']}. Nothing was checked.",
        text=body.removeprefix(spec.marker).lstrip("\n"),
    )
    return Rendered(spec.marker, body, check)


def render_not_run(editor_name: str, reason: str, head_sha: str, run: RunInfo) -> Rendered:
    """Render the comment and failed check run for a push whose review never started.

    Used when the build failed or the runner probe failed, so the review job was skipped.
    The comment replaces the previous result, which may not match this commit.

    Args:
        editor_name: ``continuity`` or ``style``.
        reason: Why the review did not run (for example ``the build failed``).
        head_sha: The commit the review did not run for.
        run: The workflow run.

    Returns:
        The comment body and a ``failure`` check payload.
    """
    spec = EDITORS[editor_name]
    context = {
        "marker": spec.marker,
        "title": spec.title,
        "reason": sanitize(reason, 300) or "no reason recorded",
        "sha": sanitize(head_sha, 40)[:7],
        "run": run.label,
        "retry": RETRY,
    }
    body = _environment().get_template("not_run.md.jinja2").render(**context)
    check = CheckPayload(
        name=spec.title,
        conclusion="failure",
        title=f"{spec.title}: did not run",
        summary=(
            f"The AI review did not run for commit {context['sha']}: "
            f"{context['reason']}. Nothing was checked."
        ),
        text=body.removeprefix(spec.marker).lstrip("\n"),
    )
    return Rendered(spec.marker, body, check)


def render_pending(editor_name: str, run: RunInfo) -> str:
    """Render the "review running" body that replaces a stale comment at job start.

    Args:
        editor_name: ``continuity`` or ``style``.
        run: The workflow run.

    Returns:
        The comment body.
    """
    spec = EDITORS[editor_name]
    return (
        _environment()
        .get_template("pending.md.jinja2")
        .render(marker=spec.marker, title=spec.title, run=run.label)
    )


# -- Build & Structure -----------------------------------------------------------------


@dataclass(frozen=True)
class BuildStats:
    """Numbers the Build comment shows."""

    sizes: tuple[tuple[str, str, int | None], ...]
    passage_count: int | None
    path_count: int | None


def collect_build_stats(dist: Path) -> BuildStats:
    """Read output sizes and counts from a ``dist/`` directory.

    Args:
        dist: The build output directory.

    Returns:
        Sizes (``None`` for a missing file) and the passage and path counts from
        ``allpaths-index.json`` (``None`` when that file is missing).

    Raises:
        BuildError: If ``allpaths-index.json`` exists but is not valid JSON.
        ArtifactValidationError: If it does not match its schema.
    """
    sizes = tuple(
        (label, name, (dist / name).stat().st_size if (dist / name).is_file() else None)
        for label, name in BUILD_OUTPUTS
    )
    index_path = dist / "allpaths-index.json"
    if not index_path.is_file():
        return BuildStats(sizes, None, None)
    index = load_artifact(index_path, "allpaths_index")
    return BuildStats(sizes, len(index["passages"]), len(index["paths"]))


def structure_conclusion(findings: Sequence[Mapping[str, Any]]) -> str:
    """``failure`` on any error, ``neutral`` on warnings, else ``success``."""
    levels = {finding["level"] for finding in findings}
    if "error" in levels:
        return "failure"
    return "neutral" if "warning" in levels else "success"


def structure_annotations(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Turn structure findings with a file into check-run annotations.

    Args:
        findings: ``nanoif check structure --format json`` output.

    Returns:
        GitHub annotation objects (plain text; GitHub does not render Markdown there).
    """
    annotations = []
    for finding in findings:
        if not finding.get("file"):
            continue
        line = finding.get("line") or 1
        annotations.append(
            {
                "path": finding["file"],
                "start_line": line,
                "end_line": line,
                "annotation_level": _ANNOTATION_LEVEL[finding["level"]],
                "title": finding["code"],
                "message": finding["message"][:4000],
            }
        )
    return annotations


def _structure_view(finding: Mapping[str, Any]) -> dict[str, Any]:
    where = sanitize(finding.get("file"), 200)
    if where and finding.get("line"):
        where = f"{where}:{finding['line']}"
    return {
        "where": where,
        "passage": sanitize(finding.get("passage"), 200),
        "code": finding["code"],
        "message": sanitize(finding["message"], 500),
    }


def _kb(size: int | None) -> str:
    return "missing" if size is None else f"{size / 1024:.1f} KB"


def render_build(
    findings: Sequence[Mapping[str, Any]] | None,
    stats: BuildStats | None,
    run: RunInfo,
    build_ok: bool,
    *,
    structure_crashed: bool = False,
) -> Rendered:
    """Render the Build & Structure sticky comment and the ``Structure`` check run.

    Args:
        findings: Structure findings (already validated against their schema), or ``None``
            when the structure check produced no result for this commit.
        stats: Output sizes and counts, or ``None`` when the build did not produce ``dist/``.
        run: The workflow run.
        build_ok: Whether the story build step succeeded.
        structure_crashed: With ``findings`` ``None``: the structure check itself failed
            (``True``) or an earlier step failed before it could run (``False``).

    Returns:
        The comment body and the ``Structure`` check payload. Without a structure result
        the comment says the check did not run, never "0 errors", and the check fails.
    """
    structure_ran = findings is not None
    by_level: dict[str, list[dict[str, Any]]] = {"error": [], "warning": [], "info": []}
    for finding in findings or ():
        by_level[finding["level"]].append(_structure_view(finding))
    errors, warnings, infos = (len(by_level[k]) for k in ("error", "warning", "info"))
    if not structure_ran and structure_crashed:
        headline = "structure check could not run"
    elif not build_ok:
        headline = "build failed"
    elif errors:
        headline = _plural(errors, "structure error")
    elif warnings:
        headline = f"built, {_plural(warnings, 'warning')}"
    else:
        headline = "built, structure clean"
    counts = []
    if stats is not None:
        counts = [
            "? passages"
            if stats.passage_count is None
            else _plural(stats.passage_count, "passage"),
            "? paths" if stats.path_count is None else _plural(stats.path_count, "path"),
        ]
    header = " · ".join(["Build", *counts, run.label])
    if structure_ran:
        structure_line = (
            f"{_plural(errors, 'error')}, {_plural(warnings, 'warning')}, "
            f"{_plural(infos, 'note')}"
        )
    else:
        structure_line = "not checked"
    context = {
        "marker": MARKER_BUILD,
        "headline": headline,
        "header": header,
        "build_ok": build_ok,
        "structure_ran": structure_ran,
        "structure_crashed": structure_crashed,
        "run": run.label,
        "structure_line": structure_line,
        "errors": by_level["error"][:MAX_LISTED],
        "errors_overflow": max(0, errors - MAX_LISTED),
        "warnings": by_level["warning"][:MAX_LISTED],
        "warnings_overflow": max(0, warnings - MAX_LISTED),
        "infos": by_level["info"][:MAX_LISTED],
        "infos_overflow": max(0, infos - MAX_LISTED),
        "sizes": [] if stats is None else [(label, name, _kb(s)) for label, name, s in stats.sizes],
    }
    body = _environment().get_template("build.md.jinja2").render(**context)
    if not structure_ran:
        title = "Structure check did not run"
        conclusion = "failure"
    else:
        title = (
            "Structure clean"
            if not findings
            else f"{_plural(errors, 'error')}, {_plural(warnings, 'warning')}"
        )
        conclusion = structure_conclusion(findings or ())
    check = CheckPayload(
        name=STRUCTURE_CHECK,
        conclusion=conclusion,
        title=title,
        summary=f"{header}\n\nStructure: {structure_line}.",
        text=body.removeprefix(MARKER_BUILD).lstrip("\n"),
        annotations=tuple(structure_annotations(findings or ())),
    )
    return Rendered(MARKER_BUILD, body, check)
