#!/usr/bin/env python3
"""
Update validation cache with creation dates for each path.
Analyzes git history to find when each path was first added.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def get_file_at_commit(commit_hash: str, file_path: str) -> dict:
    """Get the contents of a file at a specific commit."""
    try:
        result = subprocess.run(
            ['git', 'show', f'{commit_hash}:{file_path}'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {}
    except Exception as e:
        print(f"Error reading file at commit {commit_hash}: {e}", file=sys.stderr)
        return {}


def get_commit_history(file_path: str) -> list:
    """Get all commits that modified a file, from oldest to newest."""
    try:
        result = subprocess.run(
            ['git', 'log', '--all', '--format=%H %aI', '--reverse', '--', file_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            commits = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        commits.append({'hash': parts[0], 'date': parts[1]})
            return commits
        else:
            return []
    except Exception as e:
        print(f"Error getting commit history: {e}", file=sys.stderr)
        return []


def main():
    # Path to validation cache
    cache_file = Path('allpaths-validation-status.json')

    if not cache_file.exists():
        print(f"Error: {cache_file} not found", file=sys.stderr)
        sys.exit(1)

    # Load current cache
    with open(cache_file, 'r') as f:
        current_cache = json.load(f)

    # Get commit history (oldest to newest)
    print("Getting commit history...", file=sys.stderr)
    commits = get_commit_history(str(cache_file))
    print(f"Found {len(commits)} commits", file=sys.stderr)

    # Track when each path hash first appeared
    path_creation_dates = {}

    # Process commits from oldest to newest
    for i, commit_info in enumerate(commits):
        commit_hash = commit_info['hash']
        commit_date = commit_info['date']

        print(f"Processing commit {i+1}/{len(commits)}: {commit_hash[:8]} ({commit_date})", file=sys.stderr)

        # Get cache contents at this commit
        cache_at_commit = get_file_at_commit(commit_hash, str(cache_file))

        # Check each path in this commit
        for path_hash, path_data in cache_at_commit.items():
            # Skip metadata entries
            if not isinstance(path_data, dict) or 'route' not in path_data:
                continue

            # If this is the first time we've seen this path hash, record its creation date
            if path_hash not in path_creation_dates:
                # Use the commit date from this commit
                path_creation_dates[path_hash] = commit_date
                print(f"  Found new path {path_hash}: {path_data.get('route', 'unknown')[:50]}...", file=sys.stderr)

    # Update current cache with creation dates
    print(f"\nUpdating {len(path_creation_dates)} paths with creation dates...", file=sys.stderr)
    updated_count = 0

    for path_hash, path_data in current_cache.items():
        # Skip metadata entries
        if not isinstance(path_data, dict) or 'route' not in path_data:
            continue

        if path_hash in path_creation_dates:
            # Set created_date to when the path first appeared in git history
            created_date = path_creation_dates[path_hash]

            # If path doesn't have created_date or it's different, update it
            if 'created_date' not in path_data or path_data.get('created_date') != created_date:
                path_data['created_date'] = created_date
                updated_count += 1
                print(f"  {path_hash}: {created_date}", file=sys.stderr)
        else:
            # Path not found in history - use first_seen or current commit_date
            if 'created_date' not in path_data:
                # Prefer first_seen if available, otherwise use commit_date
                created_date = path_data.get('first_seen', path_data.get('commit_date'))
                if created_date:
                    path_data['created_date'] = created_date
                    updated_count += 1
                    print(f"  {path_hash}: {created_date} (from first_seen/commit_date)", file=sys.stderr)

    # Save updated cache
    print(f"\nSaving updated cache with {updated_count} new creation dates...", file=sys.stderr)
    current_cache['last_updated'] = datetime.now().isoformat()

    with open(cache_file, 'w') as f:
        json.dump(current_cache, f, indent=2)

    print(f"Done! Updated {cache_file}", file=sys.stderr)
    print(f"Total paths with creation dates: {sum(1 for p in current_cache.values() if isinstance(p, dict) and 'created_date' in p)}", file=sys.stderr)


if __name__ == '__main__':
    main()
