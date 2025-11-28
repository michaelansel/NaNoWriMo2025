"""
GitService: Centralized git operations for AllPaths generator.

This service consolidates all git subprocess calls into a single class,
making it easier to test, mock, and maintain git-related functionality.
"""

import sys
import subprocess
from pathlib import Path
from typing import Optional


class GitService:
    """Service for git operations on a repository."""

    def __init__(self, repo_root: Path):
        """
        Initialize GitService with a repository root.

        Args:
            repo_root: Path to the git repository root
        """
        self.repo_root = Path(repo_root)

    def get_file_commit_date(self, file_path: Path) -> Optional[str]:
        """
        Get the most recent commit date for a file using git log.

        Args:
            file_path: Path to the file

        Returns:
            ISO format datetime string of most recent commit, or None if unavailable

        Implementation notes:
        - Uses -m flag to include merge commits (important for PR-based workflows)
        - Returns author date (%aI) not committer date for consistency
        - 5-second timeout prevents hangs on large repos
        """
        try:
            # Get the most recent commit date for this file
            # -m: Include merge commits (without this, merge commits are skipped)
            # -1: Only get the most recent commit
            # --format=%aI: ISO 8601 author date format
            result = subprocess.run(
                ['git', 'log', '-m', '-1', '--format=%aI', '--', str(file_path)],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            else:
                return None
        except Exception as e:
            print(f"Warning: Could not get commit date for {file_path}: {e}", file=sys.stderr)
            return None

    def get_file_creation_date(self, file_path: Path) -> Optional[str]:
        """
        Get the earliest commit date for a file (when it was first added).

        Args:
            file_path: Path to the file

        Returns:
            ISO format datetime string of earliest commit, or None if unavailable
        """
        try:
            # Get all commit dates in reverse chronological order, with -m to include merge commits
            result = subprocess.run(
                ['git', 'log', '-m', '--format=%aI', '--reverse', '--', str(file_path)],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                dates = result.stdout.strip().split('\n')
                return dates[0] if dates else None
            else:
                return None
        except Exception as e:
            print(f"Warning: Could not get creation date for {file_path}: {e}", file=sys.stderr)
            return None

    def verify_ref_accessible(self, ref: str) -> bool:
        """
        Verify that a git ref is accessible in the repository.

        Args:
            ref: Git ref to verify (e.g., 'origin/main', 'HEAD')

        Returns:
            True if ref is accessible, False otherwise
        """
        try:
            print(f"[INFO] Verifying git base ref: {ref}", file=sys.stderr)
            result = subprocess.run(
                ['git', 'rev-parse', '--verify', ref],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                commit_sha = result.stdout.strip()
                print(f"[INFO] Base ref '{ref}' is accessible (commit: {commit_sha})", file=sys.stderr)
                return True
            else:
                print(f"[ERROR] Base ref '{ref}' is NOT accessible!", file=sys.stderr)
                print(f"[ERROR] Git command failed with return code: {result.returncode}", file=sys.stderr)
                if result.stderr:
                    print(f"[ERROR] Git stderr: {result.stderr.strip()}", file=sys.stderr)
                print(f"[ERROR] This will cause all paths to be incorrectly categorized as 'new'", file=sys.stderr)
                return False
        except Exception as e:
            print(f"[ERROR] Exception verifying base ref '{ref}': {e}", file=sys.stderr)
            return False

    def get_file_content_at_ref(self, file_path: Path, ref: str = 'HEAD') -> Optional[str]:
        """
        Get file content from git at a specific ref.

        Args:
            file_path: Absolute path to the file
            ref: Git ref to retrieve content from (default: HEAD)

        Returns:
            File content from the specified ref, or None if file doesn't exist in git
        """
        try:
            rel_path = file_path.relative_to(self.repo_root)
            cmd = ['git', 'show', f'{ref}:{rel_path}']
            print(f"[DEBUG] Running git command: {' '.join(cmd)}", file=sys.stderr)

            result = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                print(f"[DEBUG] Successfully retrieved git content for {rel_path} at {ref}", file=sys.stderr)
                return result.stdout
            else:
                print(f"[ERROR] Git command failed for {rel_path} at {ref}", file=sys.stderr)
                print(f"[ERROR] Return code: {result.returncode}", file=sys.stderr)
                if result.stderr:
                    print(f"[ERROR] Stderr: {result.stderr.strip()}", file=sys.stderr)
                return None
        except Exception as e:
            print(f"[ERROR] Exception getting git content for {file_path} at {ref}: {e}", file=sys.stderr)
            return None

    def file_has_changes(self, file_path: Path, base_ref: str = 'HEAD') -> bool:
        """
        Check if a file has any changes compared to a base ref.

        This is a simple check: if the file content differs from the base ref,
        it has changes. This includes content changes, not just prose changes.

        Args:
            file_path: Absolute path to the file
            base_ref: Git ref to compare against (default: HEAD)

        Returns:
            True if file has changes, False if identical or doesn't exist in git
        """
        # Get old version from git
        old_content = self.get_file_content_at_ref(file_path, base_ref)
        if old_content is None:
            # File doesn't exist in git, it's new (has changes)
            return True

        # Get current version
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                new_content = f.read()
        except Exception as e:
            print(f"[ERROR] Could not read file {file_path}: {e}", file=sys.stderr)
            return True  # Can't read, assume changed

        # Compare raw content
        return old_content != new_content
