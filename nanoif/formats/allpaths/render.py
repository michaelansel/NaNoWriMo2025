"""Text and HTML rendering for the AllPaths outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from nanoif.formats.common import format_date_for_display, html_environment
from nanoif.twee.links import display_text

if TYPE_CHECKING:
    from nanoif.formats.allpaths.generator import PathRecord

RULE = "=" * 80


def _header(record: PathRecord, total: int) -> list[str]:
    return [
        RULE,
        f"PATH {record.number} of {total}",
        RULE,
        f"Route: {' → '.join(record.passage_ids)}",
        f"Length: {len(record.route)} passages",
        f"Path ID: {record.id}",
        RULE,
        "",
    ]


def path_text(
    record: PathRecord, content: Mapping[str, str], total: int, include_metadata: bool
) -> str:
    """Render a path as prose, showing only the link the reader took at each step.

    Args:
        record: The path.
        content: Passage name to text.
        total: Total number of paths, for the header.
        include_metadata: Whether to add the path header and ``[PASSAGE: id]`` markers.

    Returns:
        The text file contents.
    """
    lines: list[str] = _header(record, total) if include_metadata else []
    for index, name in enumerate(record.route):
        if include_metadata:
            lines.append(f"[PASSAGE: {record.passage_ids[index]}]")
            lines.append("")
        next_name = record.route[index + 1] if index + 1 < len(record.route) else None
        lines.append(display_text(content[name], next_name))
        lines.append("")
    return "\n".join(lines)


def path_text_raw(record: PathRecord, content: Mapping[str, str], total: int) -> str:
    """Render a path with its Twee link markup intact, for tools that check choices.

    Args:
        record: The path.
        content: Passage name to text.
        total: Total number of paths, for the header.

    Returns:
        The text file contents.
    """
    lines = _header(record, total)
    for index, name in enumerate(record.route):
        lines.append(f"[PASSAGE: {record.passage_ids[index]}]")
        lines.append("")
        lines.append(content[name])
        lines.append("")
    return "\n".join(lines)


def render_html(
    story_title: str,
    records: Sequence[PathRecord],
    passages: Mapping[str, Mapping[str, str]],
    generated_at: datetime,
) -> str:
    """Render the browser page listing every path.

    Args:
        story_title: The story's title.
        records: The paths, in enumeration order.
        passages: The story graph's passages (name to ``{"content", "links"}``).
        generated_at: Timestamp shown in the page header.

    Returns:
        The HTML page.
    """
    env = html_environment()
    env.globals["display_text"] = display_text
    template = env.get_template("allpaths.html.jinja2")
    lengths = [len(record.route) for record in records]
    listed = [
        {
            "path": list(record.route),
            "path_hash": record.id,
            "category": record.category,
            "created_date": record.created or "",
            "commit_date": record.modified or "",
            "created_display": format_date_for_display(record.created),
            "modified_display": format_date_for_display(record.modified),
        }
        for record in records
    ]
    listed.sort(key=lambda item: item["created_date"] or "0", reverse=True)
    return template.render(
        story_name=story_title,
        generated_date=generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        total_paths=len(records),
        shortest_path=min(lengths) if lengths else 0,
        longest_path=max(lengths) if lengths else 0,
        average_length=f"{sum(lengths) / len(lengths):.1f}" if lengths else "0.0",
        paths_with_metadata=listed,
        passages=passages,
    )
