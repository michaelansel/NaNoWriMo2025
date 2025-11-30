#!/usr/bin/env python3
"""
Stage 1: Loader Module

Loads AllPaths data and prepares it for fact extraction.

Input:
    - dist/allpaths-metadata/*.txt - Story path text files
    - allpaths-validation-status.json - Path metadata
    - dist/allpaths-passage-mapping.json - Passage ID mapping

Output:
    - loaded_paths.json (intermediate artifact)

Responsibilities:
    - Load all story paths and metadata
    - Deduplicate passages (same passage in multiple paths)
    - Build mapping of passage → paths it appears in
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime


def load_allpaths_data(dist_dir: Path) -> Dict:
    """
    Load AllPaths data from text files and metadata.

    Args:
        dist_dir: Path to dist/ directory containing AllPaths output

    Returns:
        Dict with structure:
        {
            "passages": {
                "passage_name": {
                    "text": "Full passage text",
                    "appears_in_paths": ["path_id1", "path_id2"],
                    "passage_id": "hex_id",
                    "length": 5000
                }
            },
            "paths": [
                {
                    "id": "path_id",
                    "route": ["Passage1", "Passage2"],
                    "category": "new|modified|unchanged"
                }
            ],
            "metadata": {
                "total_paths": 30,
                "total_passages": 50,
                "generated_at": "2025-11-30T..."
            }
        }

    Raises:
        FileNotFoundError: If required AllPaths output is missing
        ValueError: If data is corrupted
    """
    # Check that AllPaths output exists
    metadata_dir = dist_dir / 'allpaths-metadata'
    if not metadata_dir.exists():
        raise FileNotFoundError(
            f"AllPaths output not found at {metadata_dir}. "
            f"Run 'npm run build:allpaths' first."
        )

    print(f"Loading AllPaths data from {metadata_dir}...", file=sys.stderr)

    # Load passage ID mapping (for translating hex IDs back to names)
    passage_mapping_file = dist_dir / 'allpaths-passage-mapping.json'
    passage_id_to_name = {}
    if passage_mapping_file.exists():
        with open(passage_mapping_file, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
            passage_id_to_name = mapping_data.get('id_to_name', {})

    # Load validation cache (for path metadata and categories)
    cache_file = dist_dir.parent / 'allpaths-validation-status.json'
    validation_cache = {}
    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            validation_cache = json.load(f)

    # Scan for path text files
    path_files = sorted(metadata_dir.glob('path-*.txt'))

    if not path_files:
        raise ValueError(
            f"No path files found in {metadata_dir}. "
            f"AllPaths output may be corrupted."
        )

    print(f"Found {len(path_files)} path files", file=sys.stderr)

    # Data structures
    passages = {}  # passage_name -> passage data
    paths = []  # list of path objects

    # Process each path file
    for path_file in path_files:
        # Extract path ID from filename (e.g., "path-abc12345.txt" -> "abc12345")
        path_id = path_file.stem.replace('path-', '')

        try:
            # Read path file
            with open(path_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse path file structure
            # Expected format:
            # Route: Passage1 → Passage2 → Passage3
            # ===
            # [PASSAGE: hex_id]
            # Passage1
            #
            # passage text...
            # ===
            # [PASSAGE: hex_id]
            # Passage2
            # ...

            # Extract route
            route = []
            for line in content.split('\n'):
                if line.startswith('Route:'):
                    route_str = line.replace('Route:', '').strip()
                    route = [p.strip() for p in route_str.split('→')]
                    break

            if not route:
                print(f"Warning: No route found in {path_file}, skipping", file=sys.stderr)
                continue

            # Get path metadata from validation cache
            path_info = validation_cache.get(path_id, {})
            category = path_info.get('category', 'new')

            # Add to paths list
            paths.append({
                'id': path_id,
                'route': route,
                'category': category
            })

            # Extract passages from path file
            # Split by passage markers
            passage_sections = content.split('[PASSAGE:')

            for section in passage_sections[1:]:  # Skip first empty section
                # Parse section: hex_id]\nPassage Name\n\npassage text
                lines = section.split('\n', 2)
                if len(lines) < 3:
                    continue

                # Extract passage ID (hex)
                passage_id = lines[0].strip().rstrip(']')

                # Extract passage name
                passage_name = lines[1].strip()

                # Translate passage ID to name if mapping available
                # (passage_name from file might be the hex ID, so translate it)
                if passage_id in passage_id_to_name:
                    actual_passage_name = passage_id_to_name[passage_id]
                else:
                    actual_passage_name = passage_name

                # Extract passage text
                passage_text = lines[2] if len(lines) > 2 else ''

                # Deduplicate passages
                if actual_passage_name not in passages:
                    passages[actual_passage_name] = {
                        'text': passage_text,
                        'appears_in_paths': [],
                        'passage_id': passage_id,
                        'length': len(passage_text)
                    }

                # Track which paths this passage appears in
                if path_id not in passages[actual_passage_name]['appears_in_paths']:
                    passages[actual_passage_name]['appears_in_paths'].append(path_id)

        except Exception as e:
            print(f"Warning: Error processing {path_file}: {e}", file=sys.stderr)
            print(f"Skipping this path and continuing...", file=sys.stderr)
            continue

    # Build result
    result = {
        'passages': passages,
        'paths': paths,
        'metadata': {
            'total_paths': len(paths),
            'total_passages': len(passages),
            'generated_at': datetime.now().isoformat()
        }
    }

    print(f"Loaded {len(passages)} unique passages across {len(paths)} paths", file=sys.stderr)

    return result


def main():
    """Test loader functionality."""
    import argparse

    parser = argparse.ArgumentParser(description='Test loader module')
    parser.add_argument('dist_dir', type=Path, help='Path to dist/ directory')
    parser.add_argument('--output', type=Path, help='Output JSON file (optional)')

    args = parser.parse_args()

    # Load data
    data = load_allpaths_data(args.dist_dir)

    # Print summary
    print(f"\nLoaded data summary:")
    print(f"  Total paths: {data['metadata']['total_paths']}")
    print(f"  Total passages: {data['metadata']['total_passages']}")
    print(f"  Generated at: {data['metadata']['generated_at']}")

    # Save to file if requested
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"\nSaved to {args.output}")


if __name__ == '__main__':
    main()
