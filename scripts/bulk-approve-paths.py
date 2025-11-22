#!/usr/bin/env python3
"""
Bulk approve story paths in the validation cache.

This script allows you to mark multiple paths as validated at once,
filtered by category (new, modified, unchanged) or approve all paths.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def load_cache(cache_path: Path) -> Dict:
    """Load the validation cache file."""
    if not cache_path.exists():
        print(f"Error: Cache file not found: {cache_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading cache: {e}", file=sys.stderr)
        sys.exit(1)


def save_cache(cache_path: Path, cache: Dict):
    """Save the validation cache file."""
    try:
        with open(cache_path, 'w') as f:
            json.dump(cache, f, indent=2)
        print(f"✓ Cache saved to {cache_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error saving cache: {e}", file=sys.stderr)
        sys.exit(1)


def get_paths_by_category(cache: Dict, category: str) -> List[tuple]:
    """Get list of path IDs and routes for a given category.

    Returns:
        List of (path_id, route, is_validated) tuples
    """
    paths = []
    for path_id, data in cache.items():
        if not isinstance(data, dict):
            continue

        path_category = data.get('category', 'unknown')
        if path_category == category:
            route = data.get('route', 'Unknown route')
            is_validated = data.get('validated', False)
            paths.append((path_id, route, is_validated))

    return paths


def mark_paths_validated(cache: Dict, path_ids: List[str], user: str, dry_run: bool = False) -> int:
    """Mark specified paths as validated.

    Args:
        cache: The validation cache dictionary
        path_ids: List of path IDs to mark as validated
        user: Username to record as validator
        dry_run: If True, don't actually modify the cache

    Returns:
        Number of paths marked as validated
    """
    count = 0
    timestamp = datetime.now().isoformat()

    for path_id in path_ids:
        if path_id in cache and isinstance(cache[path_id], dict):
            if not dry_run:
                cache[path_id]['validated'] = True
                cache[path_id]['validated_at'] = timestamp
                cache[path_id]['validated_by'] = user
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser(
        description='Bulk approve story paths by category',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what would be approved for modified paths
  %(prog)s --category modified --dry-run

  # Approve all modified paths
  %(prog)s --category modified --user yourname

  # Approve all new paths
  %(prog)s --category new --user yourname

  # Approve specific path IDs
  %(prog)s --paths abc12345 def67890 --user yourname
        """
    )

    parser.add_argument('--cache', type=Path,
                       default='allpaths-validation-status.json',
                       help='Path to validation cache file (default: allpaths-validation-status.json)')
    parser.add_argument('--category', choices=['new', 'modified', 'unchanged', 'all'],
                       help='Approve all paths in this category')
    parser.add_argument('--paths', nargs='+',
                       help='Specific path IDs to approve (space-separated)')
    parser.add_argument('--user', required=True,
                       help='Your username for the validated_by field')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without modifying the cache')
    parser.add_argument('--include-validated', action='store_true',
                       help='Include already-validated paths (default: skip them)')

    args = parser.parse_args()

    if not args.category and not args.paths:
        parser.error("Must specify either --category or --paths")

    # Load cache
    cache = load_cache(args.cache)

    # Determine which paths to approve
    paths_to_approve = []

    if args.paths:
        # Specific path IDs provided
        for path_id in args.paths:
            if path_id in cache and isinstance(cache[path_id], dict):
                route = cache[path_id].get('route', 'Unknown')
                is_validated = cache[path_id].get('validated', False)
                paths_to_approve.append((path_id, route, is_validated))
            else:
                print(f"Warning: Path {path_id} not found in cache", file=sys.stderr)

    elif args.category:
        # Filter by category
        if args.category == 'all':
            # Get all paths
            for path_id, data in cache.items():
                if isinstance(data, dict):
                    route = data.get('route', 'Unknown')
                    is_validated = data.get('validated', False)
                    paths_to_approve.append((path_id, route, is_validated))
        else:
            paths_to_approve = get_paths_by_category(cache, args.category)

    if not paths_to_approve:
        print(f"No paths found matching criteria", file=sys.stderr)
        sys.exit(0)

    # Filter out already-validated paths unless --include-validated
    if not args.include_validated:
        unvalidated = [(pid, route, val) for pid, route, val in paths_to_approve if not val]
        already_validated = [(pid, route, val) for pid, route, val in paths_to_approve if val]

        if already_validated:
            print(f"Skipping {len(already_validated)} already-validated path(s)", file=sys.stderr)

        paths_to_approve = unvalidated

    if not paths_to_approve:
        print("All matching paths are already validated", file=sys.stderr)
        sys.exit(0)

    # Show what will be approved
    print(f"\n{'DRY RUN - ' if args.dry_run else ''}Marking {len(paths_to_approve)} path(s) as validated:\n", file=sys.stderr)
    for i, (path_id, route, _) in enumerate(paths_to_approve[:10], 1):
        print(f"  {i}. [{path_id}] {route}", file=sys.stderr)

    if len(paths_to_approve) > 10:
        print(f"  ... and {len(paths_to_approve) - 10} more", file=sys.stderr)

    # Confirm if not dry-run
    if not args.dry_run:
        print(f"\nValidator: {args.user}", file=sys.stderr)
        response = input("\nProceed? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled", file=sys.stderr)
            sys.exit(0)

    # Mark paths as validated
    path_ids = [pid for pid, _, _ in paths_to_approve]
    count = mark_paths_validated(cache, path_ids, args.user, args.dry_run)

    # Save cache if not dry-run
    if not args.dry_run:
        save_cache(args.cache, cache)
        print(f"\n✓ Marked {count} path(s) as validated", file=sys.stderr)
    else:
        print(f"\nDRY RUN: Would mark {count} path(s) as validated", file=sys.stderr)


if __name__ == "__main__":
    main()
