"""The one place the build talks to ``git``.

Every subprocess call has a timeout and a checked return code. Results are
cached for the lifetime of the service so a build never asks git the same
question twice, and nothing here is ever called inside a per-path loop: file
dates come from a single ``git log`` over the source directory, and base-branch
files come from a single ``git cat-file --batch``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nanoif.errors import GitError


def normalize_iso_date(value: str) -> str:
    """Return a git ``%aI`` date in one form whatever the git version.

    Newer git prints a UTC offset as ``Z`` and older git as ``+00:00``; both
    become ``+00:00`` so outputs do not change with the runner's git.

    Args:
        value: A strict ISO 8601 date from git.

    Returns:
        The same instant and offset as ``datetime.isoformat`` writes it.
    """
    return datetime.fromisoformat(value).isoformat()


@dataclass(frozen=True)
class FileDates:
    """When a file first and last changed, as ISO 8601 author dates.

    Attributes:
        created: Date of the earliest commit touching the file.
        modified: Date of the most recent commit touching the file.
    """

    created: str
    modified: str


@dataclass(frozen=True)
class CommitInfo:
    """One commit with its full message and the paths it changes."""

    sha: str
    message: str
    paths: list[str]


class GitService:
    """Read-only git queries against one repository.

    Args:
        repo_root: The repository root (any directory inside it works for git,
            but paths returned by this service are relative to ``repo_root``).
        timeout_s: Seconds each git command may run before it is an error.
    """

    def __init__(self, repo_root: Path, timeout_s: float = 60.0) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.timeout_s = timeout_s
        self._rev_parse: dict[str, str] = {}
        self._file_dates: dict[str, dict[str, FileDates]] = {}
        self._list_files: dict[tuple[str, str, str], list[str]] = {}

    def _run(self, *args: str, stdin: bytes | None = None) -> bytes:
        command = ["git", *args]
        try:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                input=stdin,
                capture_output=True,
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {' '.join(args[:2])} timed out after {self.timeout_s}s") from exc
        except OSError as exc:
            raise GitError(f"could not run git: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise GitError(f"git {' '.join(args)} failed ({completed.returncode}): {detail}")
        return completed.stdout

    def rev_parse(self, ref: str) -> str:
        """Resolve a ref to a commit sha.

        Args:
            ref: Anything ``git rev-parse --verify`` accepts (``HEAD``, a sha, ``origin/main``).

        Returns:
            The full commit sha.

        Raises:
            GitError: If the ref does not resolve.
        """
        if ref not in self._rev_parse:
            output = self._run("rev-parse", "--verify", f"{ref}^{{commit}}")
            self._rev_parse[ref] = output.decode().strip()
        return self._rev_parse[ref]

    def ref_exists(self, ref: str) -> bool:
        """Return whether a ref resolves to a commit.

        Args:
            ref: The ref to test.

        Returns:
            True if :meth:`rev_parse` would succeed.
        """
        try:
            self.rev_parse(ref)
        except GitError:
            return False
        return True

    def file_dates(self, subdir: str) -> dict[str, FileDates]:
        """Return creation and modification dates for every tracked file under a directory.

        One ``git log`` call covers the whole directory; merge commits count
        (``-m``) so a file merged from a PR is dated by the merge as well.

        Args:
            subdir: Directory relative to the repository root, for example ``"src"``.

        Returns:
            Repository-relative POSIX path to its dates, for every file that has
            ever been committed under ``subdir``. Untracked files are absent.
        """
        if subdir not in self._file_dates:
            output = self._run(
                "log", "-m", "--format=%x00%H %aI", "--name-only", "--", subdir
            ).decode("utf-8", errors="replace")
            first_seen: dict[str, str] = {}
            last_seen: dict[str, str] = {}
            for chunk in output.split("\0"):
                lines = chunk.strip("\n").split("\n")
                if not lines[0]:
                    continue
                date = normalize_iso_date(lines[0].split(" ", 1)[1])
                for path in lines[1:]:
                    if not path:
                        continue
                    first_seen.setdefault(path, date)
                    last_seen[path] = date
            self._file_dates[subdir] = {
                path: FileDates(created=last_seen[path], modified=first_seen[path])
                for path in first_seen
            }
        return self._file_dates[subdir]

    def list_files(self, ref: str, subdir: str, suffix: str = ".twee") -> list[str]:
        """List files with a suffix under a directory at a ref.

        Args:
            ref: The commit to look at.
            subdir: Directory relative to the repository root.
            suffix: File name suffix to keep.

        Returns:
            Sorted repository-relative POSIX paths; empty if the directory does not exist there.

        Raises:
            GitError: If the ref does not resolve.
        """
        key = (ref, subdir, suffix)
        if key not in self._list_files:
            sha = self.rev_parse(ref)
            output = self._run("ls-tree", "-r", "--name-only", "-z", sha, "--", subdir)
            names = [name for name in output.decode("utf-8").split("\0") if name]
            self._list_files[key] = sorted(name for name in names if name.endswith(suffix))
        return self._list_files[key]

    def read_files(self, ref: str, paths: Iterable[str]) -> dict[str, str]:
        """Read several files at a ref with one ``git cat-file --batch`` call.

        Args:
            ref: The commit to read from.
            paths: Repository-relative paths.

        Returns:
            Path to its UTF-8 contents, in the order given.

        Raises:
            GitError: If the ref does not resolve or any path is missing at it.
        """
        wanted = list(paths)
        if not wanted:
            return {}
        sha = self.rev_parse(ref)
        request = "".join(f"{sha}:{path}\n" for path in wanted).encode("utf-8")
        output = self._run("cat-file", "--batch", stdin=request)
        contents: dict[str, str] = {}
        cursor = 0
        for path in wanted:
            newline = output.index(b"\n", cursor)
            header = output[cursor:newline].decode("utf-8")
            cursor = newline + 1
            fields = header.split(" ")
            if len(fields) != 3 or fields[1] != "blob":
                raise GitError(f"{path} is not a file at {ref}: {header}")
            size = int(fields[2])
            contents[path] = output[cursor : cursor + size].decode("utf-8")
            cursor += size + 1
        return contents

    def staged_files(self) -> list[str]:
        """Return paths staged in the index, relative to the repository root."""
        out = self._run("diff", "--cached", "--name-only", "-z", "--no-renames")
        return [p for p in out.decode("utf-8").split("\0") if p]

    def commits(self, base: str, head: str = "HEAD") -> list[CommitInfo]:
        """Return non-merge commits in ``base..head``, oldest first, with changed paths.

        Args:
            base: Exclusive lower bound ref.
            head: Inclusive upper bound ref.
        """
        shas = self._run("rev-list", "--reverse", "--no-merges", f"{base}..{head}")
        commits = []
        for sha in shas.decode("utf-8").split():
            message = self._run("log", "-1", "--format=%B", sha).decode("utf-8")
            names = self._run(
                "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--no-renames",
                "--root", sha,
            )
            paths = [p for p in names.decode("utf-8").split("\0") if p]
            commits.append(CommitInfo(sha=sha, message=message, paths=paths))
        return commits

SNAPSHOT_IDENTITY = ("-c", "user.name=nanoif", "-c", "user.email=nanoif@example.invalid")
"""Committer identity for throwaway snapshot repositories (never used on a real repo)."""


def snapshot_repository(root: Path, message: str, timeout_s: float = 60.0) -> tuple[str, str]:
    """Turn a directory into a fresh repository: an empty base commit, then everything in it.

    Used to evaluate a fixture story in a temporary directory so that every passage is
    ``changed`` against the base. Never call this on a working repository.

    Args:
        root: A directory that is not yet a git repository.
        message: Message of the commit holding the directory's contents.
        timeout_s: Seconds each git command may run.

    Returns:
        ``(base_sha, head_sha)``.

    Raises:
        GitError: ``root`` is already a repository, or a git command failed.
    """
    root = Path(root).resolve()
    if (root / ".git").exists():
        raise GitError(f"{root} is already a git repository")
    service = GitService(root, timeout_s=timeout_s)
    flags = (*SNAPSHOT_IDENTITY, "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null")
    service._run("init", "-q", "-b", "main")
    service._run(*flags, "commit", "-q", "--allow-empty", "-m", "empty base")
    base = service._run("rev-parse", "HEAD").decode().strip()
    service._run("add", "-A")
    service._run(*flags, "commit", "-q", "--allow-empty", "-m", message)
    head = service._run("rev-parse", "HEAD").decode().strip()
    return base, head
