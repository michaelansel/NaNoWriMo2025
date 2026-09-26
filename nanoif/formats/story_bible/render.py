"""Render ``story-bible.html`` and ``story-bible.json`` from the assembled Bible (ADR-020).

This module only renders: :func:`nanoif.bible.assemble.load_bible` reads the cache, the
overrides and ``src/`` and never calls a model. A missing cache renders the placeholder
page. A cache that exists but is invalid raises
:class:`~nanoif.errors.BibleCacheError` before anything is written, so the last good
page is never replaced by a placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from nanoif.bible.assemble import Bible, load_bible
from nanoif.formats.common import format_date_for_display, html_environment
from nanoif.git.service import GitService
from nanoif.schemas.artifacts import load_artifact, validate_artifact, write_artifact

SCHEMA_VERSION = "2.0.0"


@dataclass(frozen=True)
class StoryBibleConfig:
    """Inputs of a Story Bible build.

    Attributes:
        repo_root: The git repository root (for the source commit).
        cache_path: ``ai/story-bible-cache.json``; may not exist.
        src_dir: The story source.
        overrides_path: ``story-overrides.txt``; may not exist.
        story_graph_path: ``story_graph.json`` from ``nanoif build core`` (for the title).
        output_dir: Where ``story-bible.html`` and ``story-bible.json`` go.
        extraction_result: How the latest extraction job ended.
        generated_at: Timestamp shown on the page; defaults to now.
    """

    repo_root: Path
    cache_path: Path
    src_dir: Path
    overrides_path: Path
    story_graph_path: Path
    output_dir: Path
    extraction_result: str = "success"
    generated_at: datetime | None = None


@dataclass(frozen=True)
class StoryBibleResult:
    """What a Story Bible build wrote.

    Attributes:
        html_path: The page.
        json_path: The machine-readable Story Bible.
        bible: The assembled Bible it rendered.
    """

    html_path: Path
    json_path: Path
    bible: Bible

    @property
    def placeholder(self) -> bool:
        """True when there was no cache and the placeholder was rendered."""
        return not self.bible.cache_present


def render_html(bible: Bible, story_title: str, commit: str, generated_at: datetime) -> str:
    """Render ``story-bible.html``.

    Args:
        bible: The assembled Bible.
        story_title: Shown in the title and header.
        commit: The commit the page was built from.
        generated_at: When it was built.

    Returns:
        The HTML page; every value from the cache is escaped.
    """
    template = html_environment().get_template("story-bible.html.jinja2")
    return template.render(
        bible=bible,
        fresh=bible.freshness,
        story_title=story_title,
        commit=commit,
        generated_at=format_date_for_display(generated_at.isoformat()),
        extracted_at=format_date_for_display(bible.freshness.extracted_at),
    )


def story_bible_document(bible: Bible, commit: str, generated_at: datetime) -> dict[str, Any]:
    """Build ``story-bible.json``.

    Args:
        bible: The assembled Bible.
        commit: Full commit sha the page was built from.
        generated_at: When it was built.

    Returns:
        The document, conforming to ``story_bible.schema.json``.
    """
    return {
        "meta": {
            "generated": generated_at.isoformat(),
            "commit": commit,
            "schema_version": SCHEMA_VERSION,
        },
        **bible.to_dict(),
    }


def build_story_bible(config: StoryBibleConfig) -> StoryBibleResult:
    """Write ``story-bible.html`` and ``story-bible.json``.

    Args:
        config: Inputs; see :class:`StoryBibleConfig`.

    Returns:
        What was written.

    Raises:
        BibleCacheError: The cache exists but is invalid; nothing is written.
        BibleError: Unknown extraction result, or no story source.
        BuildError: ``story_graph.json`` is missing, or the overrides are unreadable.
        GitError: The source commit cannot be resolved.
        ArtifactValidationError: ``story-bible.json`` does not match its schema.
    """
    story_graph = load_artifact(config.story_graph_path, "story_graph")
    bible = load_bible(
        config.repo_root,
        config.cache_path,
        overrides_path=config.overrides_path,
        src=config.src_dir,
        extraction_result=config.extraction_result,
    )
    commit = GitService(config.repo_root).rev_parse("HEAD")
    generated_at = config.generated_at or datetime.now()
    document = story_bible_document(bible, commit, generated_at)
    validate_artifact(document, "story_bible")
    html = render_html(bible, story_graph["metadata"]["story_title"], commit, generated_at)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    html_path = config.output_dir / "story-bible.html"
    json_path = config.output_dir / "story-bible.json"
    write_artifact(json_path, document, "story_bible")
    html_path.write_text(html, encoding="utf-8")
    return StoryBibleResult(html_path=html_path, json_path=json_path, bible=bible)
