"""The commit gate: governed changes must move intent or say why they do not."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from nanoif.git.service import GitService

INFRA_PASSAGE_FILES = {
    "src/Start.twee",
    "src/StoryData.twee",
    "src/StoryTitle.twee",
    "src/StoryStyles.twee",
    "src/PathIdDisplay.twee",
}
GOVERNED_PREFIXES = ("nanoif/", ".github/", "scripts/", "deploy/", "landing/")
GOVERNED_FILES = {"pyproject.toml"} | INFRA_PASSAGE_FILES
INTENT_PREFIXES = ("features/", "architecture/")
INTENT_FILES = {"VISION.md", "PRINCIPLES.md", "PRIORITIES.md", "ARCHITECTURE.md"}
TRAILER_RE = re.compile(r"^Intent: unchanged \((?P<reason>[^)]*\S[^)]*)\)\s*$", re.MULTILINE)

GATE_HELP = (
    "This commit changes governed files ({files}) but no intent document "
    "(features/, architecture/, ARCHITECTURE.md, VISION.md, PRINCIPLES.md, PRIORITIES.md).\n"
    "Either update the feature note or ADR that describes this behaviour, or, if the "
    "documented intent really is unchanged, add a trailer to the commit message:\n"
    "    Intent: unchanged (<why the documented behaviour and decisions still hold>)"
)


@dataclass(frozen=True)
class CommitResult:
    """Outcome of checking one commit."""

    ok: bool
    governed: list[str]
    intent: list[str]
    message: str = ""


def classify_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """Split changed paths into governed code and intent documents.

    Args:
        paths: Repository-relative paths, in any order.

    Returns:
        ``(governed, intent)``, each in input order. Paths in neither list (tests,
        writer prose, README, ``.claude/``) need nothing from the gate.
    """
    governed = [p for p in paths if p.startswith(GOVERNED_PREFIXES) or p in GOVERNED_FILES]
    intent = [p for p in paths if p.startswith(INTENT_PREFIXES) or p in INTENT_FILES]
    return governed, intent


def check_commit(message: str, paths: list[str]) -> CommitResult:
    """Decide whether a commit with this message and these changed paths may land.

    Args:
        message: Full commit message.
        paths: Files the commit changes.

    Returns:
        ``ok`` when nothing governed changed, an intent document changed, or the
        message carries ``Intent: unchanged (<non-empty reason>)``.
    """
    governed, intent = classify_paths(paths)
    if not governed or intent or TRAILER_RE.search(message):
        return CommitResult(ok=True, governed=governed, intent=intent)
    shown = ", ".join(governed[:5]) + (" ..." if len(governed) > 5 else "")
    return CommitResult(ok=False, governed=governed, intent=intent,
                        message=GATE_HELP.format(files=shown))


def check_staged(repo: Path, message: str) -> CommitResult:
    """Check the staged changes of ``repo`` against ``message``."""
    return check_commit(message, GitService(repo).staged_files())


def check_range(repo: Path, base: str, head: str = "HEAD") -> list[tuple[str, CommitResult]]:
    """Check every non-merge commit in ``base..head``.

    Args:
        repo: Repository root.
        base: Exclusive lower bound (for a PR, the merge base with the target branch).
        head: Inclusive upper bound.

    Returns:
        ``(sha, result)`` for each failing commit, oldest first; empty when all pass.
    """
    failures = []
    for commit in GitService(repo).commits(base, head):
        result = check_commit(commit.message, commit.paths)
        if not result.ok:
            failures.append((commit.sha, result))
    return failures
