"""Helpers shared by the HTML formats."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "html"


def format_date_for_display(date_str: str | None) -> str:
    """Format an ISO 8601 date for a page.

    Args:
        date_str: An ISO 8601 date, with or without an offset, or None. A date
            without an offset is taken to be UTC already.

    Returns:
        ``YYYY-MM-DD HH:MM UTC``; ``Unknown`` for no date; the first ten
        characters for a date that does not parse.
    """
    if not date_str:
        return "Unknown"
    try:
        parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return date_str[:10]
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def html_environment() -> Environment:
    """Return the Jinja environment for ``nanoif/templates/html``, with HTML autoescaping.

    Returns:
        A configured environment.
    """
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "jinja2"]),
    )
