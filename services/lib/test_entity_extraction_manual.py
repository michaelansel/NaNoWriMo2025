#!/usr/bin/env python3
"""
Manual test script for entity extraction.

Tests the key cases from the PRD:
- "when Marcie was with us" → Extract "Marcie"
- "Miss Rosie's famous beef stew" → Extract "Miss Rosie" and "beef stew"
- "Josie fell out of a tree" → Extract "Josie"
"""

import sys
from pathlib import Path

# Add services/lib to path
sys.path.insert(0, str(Path(__file__).parent))

from story_bible_extractor import EXTRACTION_PROMPT


def main():
    """Display the extraction prompt for review."""
    print("=" * 80)
    print("ENTITY-FIRST EXTRACTION PROMPT")
    print("=" * 80)
    print()
    print(EXTRACTION_PROMPT)
    print()
    print("=" * 80)
    print("KEY TEST CASES TO VERIFY:")
    print("=" * 80)
    print()
    print("1. Dialogue mention: 'when Marcie was with us'")
    print("   Expected: Extract 'Marcie' as character")
    print()
    print("2. Possessive reference: 'Miss Rosie's famous beef stew'")
    print("   Expected: Extract 'Miss Rosie' as character AND 'beef stew' as item")
    print()
    print("3. Narrative mention: 'Josie fell out of a tree'")
    print("   Expected: Extract 'Josie' as character")
    print()
    print("=" * 80)
    print()
    print("To test with real extraction, run:")
    print("  cd /home/ubuntu/Code/NaNoWriMo2025")
    print("  python services/lib/story_bible_webhook.py --mode full")
    print()
    print("This will extract entities from all passages in the story.")
    print()


if __name__ == '__main__':
    main()
