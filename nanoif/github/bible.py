"""The ``/extract-story-bible`` sticky comment, found by ``<!-- nano:bible -->`` (ADR-020).

The command is a dry run of the pull request merged with ``main``: the comment is headed
"dry run: nothing was saved" and lists what the extraction would add, change and retire,
and what it cost. When the run could not happen or failed, the same comment says "did not
run" with the reason and shows no earlier result.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from nanoif.github.comments import MARKER_BIBLE
from nanoif.github.report import RunInfo, _environment, _plural
from nanoif.github.sanitize import sanitize

MAX_NAMED = 10
COMMAND = "/extract-story-bible"


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
