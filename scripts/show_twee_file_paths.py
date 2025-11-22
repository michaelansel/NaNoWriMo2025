#!/usr/bin/env python3
"""
Show twee files and their associated paths, sorted by path creation date.

This script reads the allpaths validation cache and displays which paths use
each twee file, along with when those paths were completed (became available).

Implementation notes:
- PURPOSE: Debug tool to understand which .twee files contribute to which paths
- USE CASE: Find which files to review when specific paths have issues
- Requires: allpaths-validation-status.json with created_date field populated
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def build_passage_to_file_mapping(source_dir: Path) -> dict:
    """Build a mapping from passage names to their source .twee files."""
    mapping = {}

    # Find all .twee files
    for twee_file in sorted(source_dir.glob('**/*.twee')):
        try:
            with open(twee_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all passage declarations (:: PassageName)
            passages_in_file = re.findall(r'^:: (.+?)(?:\s*\[.*?\])?\s*$', content, re.MULTILINE)

            for passage_name in passages_in_file:
                mapping[passage_name.strip()] = twee_file.name
        except Exception as e:
            print(f"Warning: Could not read {twee_file}: {e}")
            continue

    return mapping


def main():
    # Build passage to file mapping
    source_dir = Path('src')
    passage_to_file = build_passage_to_file_mapping(source_dir)

    # Load validation cache
    cache_file = Path('allpaths-validation-status.json')
    with open(cache_file, 'r') as f:
        cache = json.load(f)

    # Filter to real paths (those with route_hash and raw_content_fingerprint)
    real_paths = [
        (hash, data)
        for hash, data in cache.items()
        if isinstance(data, dict) and 'route_hash' in data and data.get('route_hash') and data.get('raw_content_fingerprint')
    ]

    # Group paths by twee files they use
    file_to_paths = defaultdict(list)
    for hash, data in real_paths:
        route = data.get('route', '')
        passage_names = [p.strip() for p in route.split(' → ')]
        created = data.get('created_date', 'Unknown')

        # Find all twee files used in this path
        files_in_path = set()
        for passage_name in passage_names:
            if passage_name in passage_to_file:
                files_in_path.add(passage_to_file[passage_name])

        # Add this path to each file
        for file in files_in_path:
            file_to_paths[file].append((hash, data, created))

    # Print results organized by twee file
    print('Twee files and their associated paths (sorted by path creation date):\n')
    print('=' * 80)

    for twee_file in sorted(file_to_paths.keys()):
        paths = file_to_paths[twee_file]
        # Sort paths by creation date
        paths.sort(key=lambda x: x[2])

        print(f'\n{twee_file}:')
        print(f'  Used in {len(paths)} path(s)')

        for hash, data, created in paths:
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                created_display = dt.strftime('%Y-%m-%d')
            except:
                created_display = created[:10] if len(created) >= 10 else created

            route = data.get('route', '')
            parts = route.split(' → ')
            if len(parts) > 3:
                route_display = f'{parts[0]} → ... → {parts[-1]}'
            else:
                route_display = route

            print(f'    {created_display}: {route_display}')


if __name__ == '__main__':
    main()
