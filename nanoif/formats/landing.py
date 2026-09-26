"""The landing page: ``landing/index.html`` with the story's title filled in.

The template marks each place the title goes with :data:`TITLE_MARKER`. The title comes
from ``StoryTitle`` through ``story_graph.json`` metadata, HTML-escaped, so a new season
changes one passage instead of the page.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from nanoif.errors import BuildError

TITLE_MARKER = "{{STORY_TITLE}}"


def build_landing(template: Path, story_graph: Path, out_dir: Path) -> Path:
    """Write ``<out_dir>/index.html`` from the template with the story title filled in.

    Args:
        template: ``landing/index.html``.
        story_graph: ``story_graph.json`` written by ``nanoif build core``.
        out_dir: Build output directory.

    Returns:
        The written page.

    Raises:
        BuildError: A file is missing or unreadable, or the template has no title marker.
    """
    try:
        page = template.read_text(encoding="utf-8")
        metadata = json.loads(story_graph.read_text(encoding="utf-8")).get("metadata", {})
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"landing page: {exc}") from exc
    if TITLE_MARKER not in page:
        raise BuildError(f"landing page {template} has no {TITLE_MARKER} marker")
    title = str(metadata.get("story_title") or "Untitled")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.html"
    out.write_text(page.replace(TITLE_MARKER, html.escape(title)), encoding="utf-8")
    return out
