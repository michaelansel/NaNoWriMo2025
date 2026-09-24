"""Where a build reads and writes, derived from the repository root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """The standard layout of a story repository.

    Attributes:
        repo: The repository root.
        src: Story source (``src/``).
        artifacts: Core artifacts (``lib/artifacts/``).
        dist: Build output (``dist/``).
        cache: The Story Bible extraction cache.
    """

    repo: Path
    src: Path
    artifacts: Path
    dist: Path
    cache: Path

    @classmethod
    def from_repo(
        cls,
        repo: Path,
        src: Path | None = None,
        artifacts: Path | None = None,
        dist: Path | None = None,
        cache: Path | None = None,
    ) -> ProjectPaths:
        """Build the layout for a repository, with optional overrides.

        Args:
            repo: The repository root.
            src: Override for ``<repo>/src``.
            artifacts: Override for ``<repo>/lib/artifacts``.
            dist: Override for ``<repo>/dist``.
            cache: Override for ``<repo>/story-bible-cache.json``.

        Returns:
            The layout.
        """
        return cls(
            repo=repo,
            src=src or repo / "src",
            artifacts=artifacts or repo / "lib" / "artifacts",
            dist=dist or repo / "dist",
            cache=cache or repo / "story-bible-cache.json",
        )

    @property
    def story_graph(self) -> Path:
        """``story_graph.json``."""
        return self.artifacts / "story_graph.json"

    @property
    def passages(self) -> Path:
        """``passages_deduplicated.json``."""
        return self.artifacts / "passages_deduplicated.json"

    @property
    def paperthin_html(self) -> Path:
        """The compiled story ``build core`` parses."""
        return self.dist / "story-paperthin.html"

    @property
    def lookup(self) -> Path:
        """The generated ``PathIdLookup.twee``."""
        return self.src / "PathIdLookup.twee"
