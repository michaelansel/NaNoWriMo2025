#!/usr/bin/env python3
"""
Story Bible Generator

Generates human and machine-readable story bible from AllPaths format.

Cache-first approach:
- If story-bible-cache.json exists → Render HTML/JSON from cache
- If cache missing → Generate placeholder HTML/JSON
- NEVER calls Ollama (extraction is webhook-only)
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent / 'modules'))
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from modules.loader import load_allpaths_data
from modules.html_generator import generate_html_output
from modules.json_generator import generate_json_output


def count_facts(fact_dict):
    """Count total facts across all categories."""
    total = 0
    for category_facts in fact_dict.values():
        if isinstance(category_facts, list):
            total += len(category_facts)
    return total


def load_cache(cache_file: Path) -> dict:
    """
    Load Story Bible cache from file.

    Args:
        cache_file: Path to story-bible-cache.json

    Returns:
        Cache dict or None if not found/invalid
    """
    if not cache_file.exists():
        return None

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Warning: Failed to load cache: {e}", file=sys.stderr)
        return None


def generate_placeholder_data(loaded_data):
    """
    Generate placeholder data structure when cache is unavailable.

    Args:
        loaded_data: Output from Stage 1 (loader) with passages and paths

    Returns:
        Dict with placeholder categorized structure
    """
    return {
        'constants': {},
        'variables': {},
        'characters': {},
        'conflicts': [],
        'metadata': {
            'generation_mode': 'placeholder',
            'reason': 'Story Bible cache not found (use /extract-story-bible webhook)',
            'passages_loaded': len(loaded_data.get('passages', {})),
            'paths_loaded': len(loaded_data.get('paths', [])),
            'message': (
                'Story Bible requires extraction via webhook service. '
                'Use /extract-story-bible command in PR to populate cache.'
            )
        }
    }


def main():
    """Main entry point for Story Bible generator."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Story Bible Generator - Cache-first rendering'
    )
    parser.add_argument('dist_dir', type=Path, help='Path to dist/ directory')
    parser.add_argument('--cache', type=Path, help='Path to cache file (default: story-bible-cache.json)')

    args = parser.parse_args()

    dist_dir = args.dist_dir
    cache_file = args.cache

    # Default cache location: repo root (dist_dir.parent)
    if cache_file is None:
        cache_file = dist_dir.parent / 'story-bible-cache.json'

    try:
        # ===================================================================
        # CHECK CACHE FIRST
        # ===================================================================
        print("\n" + "="*80, file=sys.stderr)
        print("CACHE CHECK - Looking for story-bible-cache.json", file=sys.stderr)
        print("="*80, file=sys.stderr)

        cache = load_cache(cache_file)

        if cache and 'categorized_facts' in cache:
            # Cache exists - use it!
            print(f"✓ Cache found: {cache_file}", file=sys.stderr)
            categorized = cache['categorized_facts']
            cache_meta = cache.get('meta', {})
            print(f"  Last extracted: {cache_meta.get('last_extracted', 'unknown')}", file=sys.stderr)
            print(f"  Total passages: {cache_meta.get('total_passages_extracted', 0)}", file=sys.stderr)
            print(f"  Total facts: {cache_meta.get('total_facts', 0)}", file=sys.stderr)
            print("  Skipping to rendering stages (no Ollama needed)", file=sys.stderr)

        else:
            # No cache - generate placeholder
            print(f"ℹ️  Cache not found: {cache_file}", file=sys.stderr)
            print("  Generating placeholder Story Bible", file=sys.stderr)
            print("  Use /extract-story-bible webhook to populate cache", file=sys.stderr)

            # Load AllPaths data for placeholder metadata
            loaded_data = load_allpaths_data(dist_dir)
            categorized = generate_placeholder_data(loaded_data)

        # ===================================================================
        # STAGE 4: GENERATE HTML
        # ===================================================================
        print("\n" + "="*80, file=sys.stderr)
        print("STAGE 4: GENERATE HTML - Creating story-bible.html", file=sys.stderr)
        print("="*80, file=sys.stderr)

        html_output = dist_dir / 'story-bible.html'
        generate_html_output(categorized, html_output)
        print(f"Generated: {html_output}", file=sys.stderr)

        # ===================================================================
        # STAGE 5: GENERATE JSON
        # ===================================================================
        print("\n" + "="*80, file=sys.stderr)
        print("STAGE 5: GENERATE JSON - Creating story-bible.json", file=sys.stderr)
        print("="*80, file=sys.stderr)

        json_output = dist_dir / 'story-bible.json'
        generate_json_output(categorized, json_output)
        print(f"Generated: {json_output}", file=sys.stderr)

        # ===================================================================
        # COMPLETE
        # ===================================================================
        print("\n" + "="*80, file=sys.stderr)
        print("=== STORY BIBLE GENERATION COMPLETE ===", file=sys.stderr)
        print("="*80, file=sys.stderr)
        print(f"HTML: {html_output}", file=sys.stderr)
        print(f"JSON: {json_output}", file=sys.stderr)
        if cache:
            print(f"Source: Cache ({cache_file})", file=sys.stderr)
        else:
            print(f"Source: Placeholder (cache not found)", file=sys.stderr)
        print("="*80 + "\n", file=sys.stderr)

        return 0

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        print(f"\nMake sure you've run 'npm run build:allpaths' first.", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
