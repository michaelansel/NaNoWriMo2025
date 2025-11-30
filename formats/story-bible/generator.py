#!/usr/bin/env python3
"""
Story Bible Generator

Generates human and machine-readable story bible from AllPaths format.

This is the main orchestrator that runs the 5-stage pipeline:
1. Load AllPaths data
2. Extract facts with AI
3. Categorize facts
4. Generate HTML output
5. Generate JSON output
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent / 'modules'))
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from modules.loader import load_allpaths_data
from modules.ai_extractor import extract_facts_with_ai
from modules.categorizer import categorize_facts
from modules.html_generator import generate_html_output
from modules.json_generator import generate_json_output


def count_facts(fact_dict):
    """Count total facts across all categories."""
    total = 0
    for category_facts in fact_dict.values():
        if isinstance(category_facts, list):
            total += len(category_facts)
    return total


def generate_placeholder_data(loaded_data):
    """
    Generate placeholder data structure when AI extraction is unavailable.

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
            'reason': 'AI extraction unavailable (Ollama service not running)',
            'passages_loaded': len(loaded_data.get('passages', {})),
            'paths_loaded': len(loaded_data.get('paths', [])),
            'message': (
                'Story Bible requires AI extraction via Ollama. '
                'To generate full Story Bible, run locally with Ollama service running, '
                'or use the continuity webhook service.'
            )
        }
    }


def main():
    """Main entry point for Story Bible generator."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Story Bible Generator - Generate human and machine-readable story bible'
    )
    parser.add_argument('dist_dir', type=Path, help='Path to dist/ directory')
    parser.add_argument('--cache', type=Path, help='Path to extraction cache file (optional)')

    args = parser.parse_args()

    dist_dir = args.dist_dir
    cache_file = args.cache

    # Default cache location
    if cache_file is None:
        cache_file = dist_dir.parent / 'story-bible-extraction-cache.json'

    try:
        # ===================================================================
        # STAGE 1: LOAD
        # ===================================================================
        print("\n" + "="*80, file=sys.stderr)
        print("STAGE 1: LOAD - Loading AllPaths data", file=sys.stderr)
        print("="*80, file=sys.stderr)

        loaded_data = load_allpaths_data(dist_dir)
        print(f"Loaded {len(loaded_data['passages'])} unique passages", file=sys.stderr)
        print(f"Across {len(loaded_data['paths'])} total paths", file=sys.stderr)

        # ===================================================================
        # STAGE 2: EXTRACT
        # ===================================================================
        print("\n" + "="*80, file=sys.stderr)
        print("STAGE 2: EXTRACT - Extracting facts with AI", file=sys.stderr)
        print("="*80, file=sys.stderr)

        try:
            extracted_facts = extract_facts_with_ai(loaded_data, cache_file=cache_file)
            print(f"Extracted facts from {len(extracted_facts['extractions'])} passages", file=sys.stderr)

            # ===================================================================
            # STAGE 3: CATEGORIZE
            # ===================================================================
            print("\n" + "="*80, file=sys.stderr)
            print("STAGE 3: CATEGORIZE - Organizing facts", file=sys.stderr)
            print("="*80, file=sys.stderr)

            categorized = categorize_facts(extracted_facts, loaded_data)
            print(f"Categorized into:", file=sys.stderr)
            print(f"  Constants: {count_facts(categorized['constants'])}", file=sys.stderr)
            print(f"  Variables: {count_facts(categorized['variables'])}", file=sys.stderr)
            print(f"  Characters: {len(categorized['characters'])}", file=sys.stderr)
            print(f"  Conflicts: {len(categorized.get('conflicts', []))}", file=sys.stderr)

        except RuntimeError as e:
            # Handle Ollama unavailability gracefully
            print(f"\n⚠️  {e}", file=sys.stderr)
            print("Generating placeholder Story Bible...", file=sys.stderr)

            categorized = generate_placeholder_data(loaded_data)
            print(f"Generated placeholder with metadata about {len(loaded_data.get('passages', {}))} passages", file=sys.stderr)

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
        print(f"Cache: {cache_file}", file=sys.stderr)
        print("="*80 + "\n", file=sys.stderr)

        return 0

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        print(f"\nMake sure you've run 'npm run build:allpaths' first.", file=sys.stderr)
        return 1

    except RuntimeError as e:
        print(f"\n❌ Error generating Story Bible: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
