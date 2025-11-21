#!/usr/bin/env python3
"""
Update validation cache with correct creation dates based on earliest passage commits.
For each path, finds the earliest commit date among all passages in that path.
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime


def get_file_commit_date(file_path: Path, earliest: bool = True) -> str:
    """Get the earliest or most recent commit date for a file."""
    try:
        # Get commit date for this file
        # Use -m to include merge commits, --follow to track renames
        if earliest:
            result = subprocess.run(
                ['git', 'log', '--all', '-m', '--format=%aI', '--reverse', '--', str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            # With --reverse, first entry is the earliest
            if result.returncode == 0 and result.stdout.strip():
                dates = result.stdout.strip().split('\n')
                return dates[0] if dates else None
            else:
                return None
        else:
            result = subprocess.run(
                ['git', 'log', '--all', '-m', '-1', '--format=%aI', '--', str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
            else:
                return None
    except Exception as e:
        print(f"Error getting commit date for {file_path}: {e}", file=sys.stderr)
        return None


def build_passage_to_file_mapping(source_dir: Path) -> dict:
    """Build a mapping from passage names to their source .twee files."""
    mapping = {}

    # Find all .twee files
    for twee_file in source_dir.glob('**/*.twee'):
        try:
            with open(twee_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all passage declarations (:: PassageName)
            passages_in_file = re.findall(r'^:: (.+?)(?:\s*\[.*?\])?\s*$', content, re.MULTILINE)

            for passage_name in passages_in_file:
                mapping[passage_name.strip()] = twee_file
        except Exception as e:
            print(f"Warning: Could not read {twee_file}: {e}", file=sys.stderr)
            continue

    return mapping


def get_path_creation_date(path_route: str, passage_to_file: dict) -> str:
    """
    Get the date when a path became fully available (most recent passage).
    This represents when the path was completed, not when it was started.
    """
    # Parse the route string to get passage names
    passage_names = [p.strip() for p in path_route.split('→')]

    commit_dates = []
    for passage_name in passage_names:
        if passage_name not in passage_to_file:
            print(f"  Warning: Passage '{passage_name}' not found in source files", file=sys.stderr)
            continue

        file_path = passage_to_file[passage_name]
        commit_date = get_file_commit_date(file_path, earliest=True)

        if commit_date:
            commit_dates.append(commit_date)

    # Return the most recent date - when the path became complete
    if commit_dates:
        return max(commit_dates)
    else:
        return None


def main():
    # Path to validation cache
    cache_file = Path('allpaths-validation-status.json')

    if not cache_file.exists():
        print(f"Error: {cache_file} not found", file=sys.stderr)
        sys.exit(1)

    # Load current cache
    print("Loading validation cache...", file=sys.stderr)
    with open(cache_file, 'r') as f:
        current_cache = json.load(f)

    # Build passage-to-file mapping
    print("Building passage-to-file mapping...", file=sys.stderr)
    source_dir = Path('src')
    passage_to_file = build_passage_to_file_mapping(source_dir)
    print(f"Found {len(passage_to_file)} passages in source files", file=sys.stderr)

    # Update creation dates for all paths
    print("\nUpdating creation dates based on earliest passage commits...", file=sys.stderr)
    updated_count = 0
    total_paths = 0

    for path_hash, path_data in current_cache.items():
        # Skip metadata entries
        if not isinstance(path_data, dict) or 'route' not in path_data:
            continue

        total_paths += 1
        route = path_data['route']

        # Get the earliest commit date for this path
        creation_date = get_path_creation_date(route, passage_to_file)

        if creation_date:
            # Update if different from current value
            current_created = path_data.get('created_date')
            if current_created != creation_date:
                path_data['created_date'] = creation_date
                updated_count += 1
                print(f"  {path_hash}: {creation_date} (was: {current_created})", file=sys.stderr)
        else:
            print(f"  Warning: Could not determine creation date for {path_hash}", file=sys.stderr)

    # Save updated cache
    print(f"\nSaving updated cache with {updated_count} modified creation dates...", file=sys.stderr)
    current_cache['last_updated'] = datetime.now().isoformat()

    with open(cache_file, 'w') as f:
        json.dump(current_cache, f, indent=2)

    print(f"\nDone! Updated {cache_file}", file=sys.stderr)
    print(f"Total paths processed: {total_paths}", file=sys.stderr)
    print(f"Creation dates modified: {updated_count}", file=sys.stderr)
    print(f"Paths with creation dates: {sum(1 for p in current_cache.values() if isinstance(p, dict) and 'created_date' in p)}", file=sys.stderr)


if __name__ == '__main__':
    main()
