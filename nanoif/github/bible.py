"""The Story Bible sticky comment, found by ``<!-- nano:bible -->`` (ADR-020, ADR-026).

Two jobs write it, one comment per pull request:

- ``/extract-story-bible`` is a dry run of the pull request merged with ``main``: the
  comment is headed "dry run: nothing was saved" and lists what the extraction would add,
  change and retire, and what it cost.
- Every push's AI job extracts the pull request's passages for its preview Story Bible
  (ADR-026). The comment names the head commit and where the preview is, and a
  ``Story Bible preview`` check run on that commit succeeds only when every passage was
  read (or there was nothing to read).

When a run could not happen or failed, the comment says "did not run" with the reason and
shows no earlier result.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from nanoif.github.comments import MARKER_BIBLE
from nanoif.github.report import CheckPayload, Rendered, RunInfo, _environment, _plural
from nanoif.github.sanitize import sanitize

MAX_NAMED = 10
COMMAND = "/extract-story-bible"
PREVIEW_CHECK = "Story Bible preview"
PREVIEW_ARTIFACT = "story-bible-preview"
PREVIEW_TEMPLATE = "bible_preview.md.jinja2"


def _cost(usage: Mapping[str, Any]) -> str:
    if not usage.get("usd_known"):
        return "cost unknown"
    return f"${float(usage.get('usd', 0.0)):.4f}"


def _named(count_label: str, names: Sequence[str]) -> str:
    if not names:
        return f"0 {count_label}"
    shown = ", ".join(sanitize(name, 120) for name in names[:MAX_NAMED])
    more = f" and {len(names) - MAX_NAMED} more" if len(names) > MAX_NAMED else ""
    return f"{len(names)} {count_label} ({shown}{more})"


def render_bible_diff(diff: Mapping[str, Any], run: RunInfo) -> str:
    """Render the dry-run comment from ``bible-diff.json``.

    Args:
        diff: A validated ``bible_diff`` artifact.
        run: The workflow run.

    Returns:
        The comment body, starting with the marker.
    """
    usage = diff["usage"]
    model = ""
    if usage.get("profile") or usage.get("model"):
        model = f"{sanitize(str(usage.get('profile') or '?'), 60)} "
        model += f"({sanitize(str(usage.get('model') or '?'), 120)})"
    header = " · ".join(
        part
        for part in (
            COMMAND,
            diff["mode"],
            f"{_plural(len(diff['passages_read']), 'passage')} read",
            f"{_plural(int(usage.get('calls', 0)), 'call')}, {_cost(usage)}",
            model,
            run.label,
        )
        if part
    )
    base = diff.get("base")
    if base:
        compared = (
            f"Compared with the saved extraction of {sanitize(base['extracted_at'][:10], 20)} "
            f"({sanitize(base['commit'][:8], 20)})."
        )
    else:
        compared = "There is no saved extraction yet, so everything read would be new."
    entities, facts, conflicts = diff["entities"], diff["facts"], diff["conflicts"]
    context = {
        "marker": MARKER_BIBLE,
        "headline": "dry run: nothing was saved",
        "header": header,
        "ran": True,
        "reason": "",
        "base": compared,
        "up_to_date": diff["status"] == "up_to_date",
        "entities": (
            f"{_named('added', entities['added'])}, {_named('changed', entities['changed'])}, "
            f"{_named('removed', entities['removed'])}"
        ),
        "facts": (
            f"{len(facts['added'])} added, {len(facts['reworded'])} reworded, "
            f"{len(facts['retired'])} retired"
        ),
        "conflicts": (
            f"{_named('added', conflicts['added'])}, {_named('retired', conflicts['retired'])}"
        ),
        "read": [sanitize(name, 200) for name in diff["passages_read"]],
        "deleted": [sanitize(name, 200) for name in diff["passages_deleted"]],
        "failed": [
            {"passage": sanitize(item["passage"], 200), "reason": sanitize(item["reason"], 300)}
            for item in diff["passages_failed"]
        ],
        "pending": [
            {"entity": sanitize(item["entity"], 200), "reason": sanitize(item["reason"], 300)}
            for item in diff["pending"]
        ],
    }
    return _environment().get_template("bible.md.jinja2").render(**context)


def render_bible_not_run(reason: str, run: RunInfo) -> str:
    """Render the comment for a dry run that did not happen or failed.

    Args:
        reason: Why, for a writer (runner offline, spend cap, a failed run).
        run: The workflow run.

    Returns:
        The comment body, starting with the marker.
    """
    return _environment().get_template("bible.md.jinja2").render(
        marker=MARKER_BIBLE,
        headline="did not run",
        header=" · ".join((COMMAND, run.label)),
        ran=False,
        reason=sanitize(reason, 500) or "no reason recorded",
    )


def _model(usage: Mapping[str, Any]) -> str:
    if not (usage.get("profile") or usage.get("model")):
        return ""
    return (
        f"{sanitize(str(usage.get('profile') or '?'), 60)} "
        f"({sanitize(str(usage.get('model') or '?'), 120)})"
    )


def _preview_check(headline: str, header: str, body: str, conclusion: str) -> CheckPayload:
    return CheckPayload(
        name=PREVIEW_CHECK,
        conclusion=conclusion,
        title=f"{PREVIEW_CHECK}: {headline}",
        summary=header,
        text=body.removeprefix(MARKER_BIBLE).lstrip("\n"),
    )


def render_bible_preview(diff: Mapping[str, Any], run: RunInfo, head_sha: str) -> Rendered:
    """Render the preview comment and check run from the preview's ``bible-diff.json``.

    Args:
        diff: A validated ``bible_diff`` artifact of ``bible extract --preview``.
        run: The workflow run that uploaded the ``story-bible-preview`` artifact.
        head_sha: The pull request head the preview is for.

    Returns:
        The comment (starting with the marker) and the ``Story Bible preview`` check run:
        ``success`` when every planned passage was read or none needed reading,
        ``failure`` when the run was partial.
    """
    usage = diff["usage"]
    sha = sanitize(head_sha, 40)[:7]
    status = diff["status"]
    failed = [
        {"passage": sanitize(item["passage"], 200), "reason": sanitize(item["reason"], 300)}
        for item in diff["passages_failed"]
    ]
    if status == "up_to_date":
        headline = "Nothing to read"
    elif status == "partial" and failed:
        headline = f"partial preview, {_plural(len(failed), 'passage')} not read"
    elif status == "partial":
        headline = "partial preview, some names not resolved"
    else:
        headline = "preview of this pull request's passages"
    header = " · ".join(
        part
        for part in (
            PREVIEW_CHECK,
            f"commit {sha}",
            f"{_plural(len(diff['passages_read']), 'passage')} read",
            f"{_plural(int(usage.get('calls', 0)), 'call')}, {_cost(usage)}",
            _model(usage),
            run.label,
        )
        if part
    )
    hits = diff["store"]["hits"]
    reused = ""
    if hits:
        shown = ", ".join(f"*{sanitize(name, 120)}*" for name in hits[:MAX_NAMED])
        more = f" and {len(hits) - MAX_NAMED} more" if len(hits) > MAX_NAMED else ""
        its = "its" if len(hits) == 1 else "their"
        reused = (
            f"{_plural(len(hits), 'passage')} already read in {its} exact text, at no cost "
            f"({shown}{more})"
        )
    entities, facts = diff["entities"], diff["facts"]
    body = _environment().get_template(PREVIEW_TEMPLATE).render(
        marker=MARKER_BIBLE,
        headline=headline,
        header=header,
        ran=True,
        reason="",
        sha=sha,
        up_to_date=status == "up_to_date",
        artifact=PREVIEW_ARTIFACT,
        run=run.label,
        entities=(
            f"{_named('new', entities['added'])}, {_named('changed', entities['changed'])}, "
            f"{_named('gone', entities['removed'])}"
        ),
        facts=(
            f"{len(facts['added'])} new, {len(facts['reworded'])} reworded, "
            f"{len(facts['retired'])} retired"
        ),
        reused=reused,
        read=[sanitize(name, 200) for name in diff["passages_read"]],
        failed=failed,
        pending=[
            {"entity": sanitize(item["entity"], 200), "reason": sanitize(item["reason"], 300)}
            for item in diff["pending"]
        ],
    )
    conclusion = "failure" if status == "partial" else "success"
    return Rendered(MARKER_BIBLE, body, _preview_check(headline, header, body, conclusion))


def render_bible_preview_not_run(reason: str, run: RunInfo, head_sha: str) -> Rendered:
    """Render the preview comment and failed check run for a push it did not run for.

    Used when the runner is hosted, the review never started (``ai-review-not-run``), the
    spend cap stopped the extraction (the reason carries the reset date), or the
    extraction failed. The comment replaces the previous push's preview.

    Args:
        reason: Why, for a writer.
        run: The workflow run.
        head_sha: The pull request head it did not run for.

    Returns:
        The comment and a ``failure`` check run.
    """
    sha = sanitize(head_sha, 40)[:7]
    header = " · ".join((PREVIEW_CHECK, f"commit {sha}", run.label))
    headline = "did not run"
    body = _environment().get_template(PREVIEW_TEMPLATE).render(
        marker=MARKER_BIBLE,
        headline=headline,
        header=header,
        ran=False,
        reason=sanitize(reason, 500) or "no reason recorded",
        sha=sha,
    )
    return Rendered(MARKER_BIBLE, body, _preview_check(headline, header, body, "failure"))
