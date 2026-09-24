"""Typed errors raised by the ``nanoif`` package.

Every failure a caller may need to distinguish has its own class. Nothing in the
package returns an empty or "no issues" result because something failed.
"""

from __future__ import annotations


class NanoifError(Exception):
    """Base class for every error raised by ``nanoif``."""


class StoryParseError(NanoifError):
    """Tweego HTML or Twee source could not be turned into a story graph."""


class GraphError(NanoifError):
    """A story graph is unusable for path enumeration (for example no start passage)."""


class ArtifactValidationError(NanoifError):
    """An artifact does not conform to its JSON schema."""


class GitError(NanoifError):
    """A git command failed, timed out, or a ref could not be resolved."""


class BuildError(NanoifError):
    """A build step could not run because an input was missing or inconsistent."""


class LintError(NanoifError):
    """A path given to the linter does not exist, is not a ``.twee`` file, or cannot be read."""
