#!/usr/bin/env python3
"""
Stage 1: Loader Module

Loads passage data from core library artifacts for fact extraction.

Input:
    - lib/artifacts/passages_deduplicated.json - Deduplicated passages from core library

Output:
    - loaded_passages dict (in-memory)

Responsibilities:
    - Load deduplicated passages from core library
    - Prepare passage data for fact extraction
    - No longer depends on AllPaths format (removes inter-format dependency)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime


def load_passages_from_core_library(project_dir: Path) -> Dict:
    """
    Load deduplicated passages from core library artifacts.

    Args:
        project_dir: Path to project root directory

    Returns:
        Dict with structure:
        {
            "passages": {
                "passage_name": {
                    "text": "Full passage text",
                    "content_hash": "abc123...",
                    "length": 5000
                }
            },
            "metadata": {
                "total_passages": 50,
                "generated_at": "2025-11-30T...",
                "source": "core_library"
            }
        }

    Raises:
        FileNotFoundError: If core library artifacts not found
    """
    # Load from core library artifacts
    passages_file = project_dir / 'lib' / 'artifacts' / 'passages_deduplicated.json'

    if not passages_file.exists():
        raise FileNotFoundError(
            f"Core library artifact not found: {passages_file}\n"
            f"Run 'npm run build:core' first to generate core artifacts."
        )

    print(f"Loading passages from core library: {passages_file}", file=sys.stderr)

    with open(passages_file, 'r', encoding='utf-8') as f:
        passages_data = json.load(f)

    # Convert passages list to dict keyed by name
    passages = {}
    for passage in passages_data.get('passages', []):
        passage_name = passage['name']
        passages[passage_name] = {
            'text': passage['content'],
            'content_hash': passage.get('content_hash', ''),
            'length': len(passage['content'])
        }

    result = {
        'passages': passages,
        'metadata': {
            'total_passages': len(passages),
            'generated_at': datetime.now().isoformat(),
            'source': 'core_library'
        }
    }

    print(f"Loaded {len(passages)} passages from core library", file=sys.stderr)

    return result


def load_allpaths_data(dist_dir: Path) -> Dict:
    """
    Load passage data (legacy interface for backward compatibility).

    Now loads from core library instead of AllPaths.

    Args:
        dist_dir: Path to dist/ directory (used to find project root)

    Returns:
        Dict with passages and metadata

    Raises:
        FileNotFoundError: If required core library output is missing
        ValueError: If data is corrupted
    """
    # Get project root (dist_dir is typically project_root/dist)
    project_dir = dist_dir.parent

    # Load from core library
    return load_passages_from_core_library(project_dir)


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
