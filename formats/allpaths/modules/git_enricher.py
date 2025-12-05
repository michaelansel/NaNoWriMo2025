"""
Git Enricher Module - Stage 3 of AllPaths Pipeline

Enriches paths with git metadata: file mappings, commit dates, creation dates.

This module takes paths.json output and adds git version control metadata
to each path, producing paths_enriched.json.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from lib.git_service import GitService


def build_passage_to_file_mapping(source_dir: Path) -> Dict[str, Path]:
    """
    Build a mapping from passage names to their source .twee files.

    Scans all .twee files in source_dir (recursively) and parses passage
    declarations to create a mapping.

    Args:
        source_dir: Directory containing .twee source files

    Returns:
        Dict mapping passage name -> file path

    Example:
        >>> mapping = build_passage_to_file_mapping(Path('src'))
        >>> mapping['Start']
        PosixPath('src/story.twee')
    """
    mapping = {}

    # Find all .twee files
    for twee_file in source_dir.glob('**/*.twee'):
        try:
            with open(twee_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all passage declarations (:: PassageName or ::PassageName)
            # Allow optional space after :: to handle both formats
            # Also handle optional tags in brackets [tag1 tag2]
            passages_in_file = re.findall(r'^::\s*(.+?)(?:\s*\[.*?\])?\s*$', content, re.MULTILINE)

            for passage_name in passages_in_file:
                mapping[passage_name.strip()] = twee_file
        except Exception as e:
            # Skip files that can't be read
            print(f"Warning: Could not read {twee_file}: {e}", file=sys.stderr)
            continue

    return mapping


def get_file_commit_date(file_path: Path, repo_root: Path) -> Optional[str]:
    """
    Get the most recent commit date for a file using git log.

    Args:
        file_path: Path to the file
        repo_root: Path to git repository root

    Returns:
        ISO format datetime string of most recent commit, or None if unavailable
    """
    git_service = GitService(repo_root)
    return git_service.get_file_commit_date(file_path)


def get_file_creation_date(file_path: Path, repo_root: Path) -> Optional[str]:
    """
    Get the earliest commit date for a file (when it was first added).

    Args:
        file_path: Path to the file
        repo_root: Path to git repository root

    Returns:
        ISO format datetime string of earliest commit, or None if unavailable
    """
    git_service = GitService(repo_root)
    return git_service.get_file_creation_date(file_path)


def get_path_commit_date(path: List[str], passage_to_file: Dict[str, Path],
                        repo_root: Path) -> Optional[str]:
    """
    Get the most recent commit date among all passages in a path.

    Args:
        path: List of passage names in the path
        passage_to_file: Mapping from passage names to file paths
        repo_root: Path to git repository root

    Returns:
        ISO format datetime string of most recent commit, or None if unavailable
    """
    commit_dates = []

    for passage_name in path:
        if passage_name not in passage_to_file:
            continue

        file_path = passage_to_file[passage_name]
        commit_date = get_file_commit_date(file_path, repo_root)

        if commit_date:
            commit_dates.append(commit_date)

    # Return the most recent date
    if commit_dates:
        return max(commit_dates)
    else:
        return None


def get_path_creation_date(path: List[str], passage_to_file: Dict[str, Path],
                          repo_root: Path) -> Optional[str]:
    """
    Get the date when a path became fully available (complete).
    This finds the most recent creation date among all passages in the path.

    Args:
        path: List of passage names in the path
        passage_to_file: Mapping from passage names to file paths
        repo_root: Path to git repository root

    Returns:
        ISO format datetime string of when path became complete, or None if unavailable
    """
    creation_dates = []

    for passage_name in path:
        if passage_name not in passage_to_file:
            continue

        file_path = passage_to_file[passage_name]
        creation_date = get_file_creation_date(file_path, repo_root)

        if creation_date:
            creation_dates.append(creation_date)

    # Return the most recent creation date - when the path became complete
    if creation_dates:
        return max(creation_dates)
    else:
        return None


def enrich_paths(paths_data: Dict, source_dir: Path, repo_root: Path) -> Dict:
    """
    Enrich paths with git metadata.

    Takes paths.json data structure and adds git version control metadata
    to each path, producing paths_enriched.json structure.

    Args:
        paths_data: Dict from paths.json with 'paths' and 'statistics'
        source_dir: Directory containing .twee source files
        repo_root: Path to git repository root

    Returns:
        Dict matching paths_enriched.json schema with git_metadata added to each path

    Example:
        >>> paths_data = {
        ...     'paths': [{'id': 'abc12345', 'route': ['Start', 'End'], 'content': {...}}],
        ...     'statistics': {...}
        ... }
        >>> enriched = enrich_paths(paths_data, Path('src'), Path('.'))
        >>> enriched['paths'][0]['git_metadata']
        {'files': [...], 'commit_date': '2025-11-20T...', ...}
    """
    # Build passage-to-file mapping
    passage_to_file = build_passage_to_file_mapping(source_dir)
    print(f"Mapped {len(passage_to_file)} passages to source files", file=sys.stderr)

    # Create enriched paths structure
    enriched_paths = []

    for path_data in paths_data['paths']:
        route = path_data['route']

        # Collect unique files for this path
        files_in_path = []
        seen_files = set()
        passage_to_file_for_path = {}

        for passage_name in route:
            if passage_name in passage_to_file:
                file_path = passage_to_file[passage_name]

                # Build passage-to-file mapping for this path
                # Convert to relative path for JSON output
                relative_path = str(file_path.relative_to(repo_root))
                passage_to_file_for_path[passage_name] = relative_path

                # Track unique files
                if relative_path not in seen_files:
                    files_in_path.append(relative_path)
                    seen_files.add(relative_path)

        # Get commit and creation dates for the path
        commit_date = get_path_commit_date(route, passage_to_file, repo_root)
        creation_date = get_path_creation_date(route, passage_to_file, repo_root)

        # Create enriched path with git metadata
        enriched_path = {
            'id': path_data['id'],
            'route': path_data['route'],
            'content': path_data['content'],
            'git_metadata': {
                'files': files_in_path,
                'commit_date': commit_date,
                'created_date': creation_date,
                'passage_to_file': passage_to_file_for_path
            }
        }

        enriched_paths.append(enriched_path)

    # Return enriched structure
    return {
        'paths': enriched_paths,
        'statistics': paths_data['statistics']
    }
