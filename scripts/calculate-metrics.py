#!/usr/bin/env python3
"""
Writing Metrics & Statistics Calculator
Analyzes story from core library artifacts to compute word count statistics.
Now reads from story_graph.json instead of parsing Twee files directly.
"""

import re
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from statistics import mean, median


# =============================================================================
# REGEX PATTERNS FOR HARLOWE SYNTAX STRIPPING
# =============================================================================

# Harlowe macros: (macro-name: args)
HARLOWE_MACRO = re.compile(r'\([a-z\-]+:.*?\)', re.IGNORECASE)

# Links: [[Display->Target]] or [[Target]]
HARLOWE_LINK_WITH_DISPLAY = re.compile(r'\[\[(.+?)->(.+?)\]\]')
HARLOWE_LINK_SIMPLE = re.compile(r'\[\[(.+?)\]\]')

# HTML tags
HTML_TAG = re.compile(r'<[^>]+>')

# Passage header: :: Name [tags]
PASSAGE_HEADER = re.compile(r'^::\s+.*$', re.MULTILINE)


# =============================================================================
# WORD COUNTING FUNCTIONS
# =============================================================================

def strip_harlowe_syntax(text: str) -> str:
    """
    Remove Harlowe macros, link markup, and HTML tags from text.

    Args:
        text: Raw text from a passage

    Returns:
        Cleaned prose text with only readable content

    Example:
        >>> strip_harlowe_syntax("Hello (set: $foo to 5) world")
        "Hello  world"
        >>> strip_harlowe_syntax("Click [[here->Target]] to continue")
        "Click here to continue"
    """
    # Replace links with display text (preserve readable text)
    text = HARLOWE_LINK_WITH_DISPLAY.sub(r'\1', text)  # [[Display->Target]] -> Display
    text = HARLOWE_LINK_SIMPLE.sub(r'\1', text)        # [[Target]] -> Target

    # Remove Harlowe macros
    text = HARLOWE_MACRO.sub('', text)

    # Remove HTML tags
    text = HTML_TAG.sub('', text)

    return text


def count_words(text: str) -> int:
    """
    Count words in cleaned prose text.

    Args:
        text: Cleaned text (after stripping Harlowe syntax)

    Returns:
        Number of words (whitespace-separated tokens)

    Example:
        >>> count_words("This is a test")
        4
    """
    # Split by whitespace and count non-empty tokens
    words = text.split()
    return len(words)


# =============================================================================
# TWEE FILE PARSING
# =============================================================================

class Passage:
    """Represents a single passage in a Twee file."""

    def __init__(self, name: str, content: str):
        self.name = name
        self.raw_content = content
        self.cleaned_content = strip_harlowe_syntax(content)
        self.word_count = count_words(self.cleaned_content)

    def to_dict(self) -> Dict:
        """Convert passage to dictionary for JSON output."""
        return {
            'name': self.name,
            'word_count': self.word_count,
        }


class TweeFile:
    """Represents a Twee file with its passages."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.passages: List[Passage] = []
        self._parse_file()

    def _parse_file(self):
        """Parse Twee file and extract passages."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Warning: Could not read {self.file_path}: {e}", file=sys.stderr)
            return

        # Split by passage headers
        # Pattern: :: PassageName [optional tags]
        passage_pattern = re.compile(r'^::\s+([^\[\n]+?)(?:\s+\[.*?\])?\s*$', re.MULTILINE)

        # Find all passage headers
        matches = list(passage_pattern.finditer(content))

        for i, match in enumerate(matches):
            passage_name = match.group(1).strip()

            # Extract content from after this header to before next header (or end of file)
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            passage_content = content[start:end].strip()

            # Create passage object
            passage = Passage(passage_name, passage_content)
            self.passages.append(passage)

    @property
    def word_count(self) -> int:
        """Total word count for this file."""
        return sum(p.word_count for p in self.passages)

    def to_dict(self) -> Dict:
        """Convert file to dictionary for JSON output."""
        return {
            'file': self.file_path.name,
            'word_count': self.word_count,
            'passage_count': len(self.passages),
        }


# =============================================================================
# FILE FILTERING
# =============================================================================

# Special files to always exclude
EXCLUDED_FILES = {'StoryData.twee', 'StoryTitle.twee', 'StoryStyles.twee'}


def matches_prefix(filename: str, prefix: str) -> bool:
    """
    Check if filename starts with prefix (case-insensitive).

    Args:
        filename: Name of file to check
        prefix: Prefix to match

    Returns:
        True if filename starts with prefix
    """
    return filename.lower().startswith(prefix.lower())


def filter_files(files: List[Path], include: List[str], exclude: List[str]) -> List[Path]:
    """
    Apply include/exclude filters to file list.

    Args:
        files: List of file paths
        include: List of prefixes to include (if empty, include all)
        exclude: List of prefixes to exclude

    Returns:
        Filtered list of file paths

    Logic:
    1. Remove special files (StoryData, StoryTitle, StoryStyles)
    2. If include specified: keep only files matching any include prefix
    3. Apply exclude: remove files matching any exclude prefix
    """
    # Remove special files
    files = [f for f in files if f.name not in EXCLUDED_FILES]

    # Apply include filter
    if include:
        files = [f for f in files if any(matches_prefix(f.name, p) for p in include)]

    # Apply exclude filter
    if exclude:
        files = [f for f in files if not any(matches_prefix(f.name, p) for p in exclude)]

    return files


# =============================================================================
# STATISTICS CALCULATION
# =============================================================================

def calculate_statistics(values: List[int]) -> Dict:
    """
    Compute min, mean, median, max statistics.

    Args:
        values: List of numeric values

    Returns:
        Dict with 'min', 'mean', 'median', 'max' keys
    """
    if not values:
        return {'min': 0, 'mean': 0.0, 'median': 0.0, 'max': 0}

    return {
        'min': min(values),
        'mean': mean(values),
        'median': median(values),
        'max': max(values),
    }


def generate_distribution(values: List[int]) -> Dict[str, int]:
    """
    Bucket values into ranges for distribution.

    Args:
        values: List of numeric values

    Returns:
        Dict mapping range label to count
    """
    buckets = [
        (0, 100, "0-100"),
        (101, 300, "101-300"),
        (301, 500, "301-500"),
        (501, 1000, "501-1000"),
        (1001, float('inf'), "1000+")
    ]

    distribution = {label: 0 for _, _, label in buckets}

    for value in values:
        for min_val, max_val, label in buckets:
            if min_val <= value <= max_val:
                distribution[label] += 1
                break

    return distribution


# =============================================================================
# METRICS COMPUTATION
# =============================================================================

def calculate_metrics_from_story_graph(
    story_graph: Dict,
    top_n: int = 5
) -> Dict:
    """
    Calculate writing metrics from story_graph.json.

    Args:
        story_graph: Story graph dict from core library
        top_n: Number of top passages to include

    Returns:
        Dict containing all metrics
    """
    if not story_graph.get('passages'):
        return {
            'error': 'No passages found in story graph',
            'total_words': 0,
            'file_count': 0,
            'passage_count': 0,
        }

    # Extract passages and calculate word counts
    all_passages = []
    for name, passage_data in story_graph['passages'].items():
        content = passage_data['content']
        passage = Passage(name, content)
        all_passages.append(passage)

    # Calculate statistics
    total_words = sum(p.word_count for p in all_passages)
    passage_word_counts = [p.word_count for p in all_passages]

    passage_stats = calculate_statistics(passage_word_counts)

    # Note: File stats not available from story_graph.json
    # Would need passage_mapping.json to group by file
    file_stats = {'min': 0, 'mean': 0.0, 'median': 0.0, 'max': 0}
    file_distribution = {"0-100": 0, "101-300": 0, "301-500": 0, "501-1000": 0, "1000+": 0}

    passage_distribution = generate_distribution(passage_word_counts)

    # Find top N longest passages
    top_passages = sorted(all_passages, key=lambda p: p.word_count, reverse=True)[:top_n]

    return {
        'total_words': total_words,
        'file_count': 0,  # Not available from story_graph alone
        'passage_count': len(all_passages),
        'passage_stats': passage_stats,
        'file_stats': file_stats,
        'passage_distribution': passage_distribution,
        'file_distribution': file_distribution,
        'top_passages': [p.to_dict() for p in top_passages],
        'files': [],  # Not available from story_graph alone
    }


def calculate_metrics(
    src_dir: Path,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    top_n: int = 5
) -> Dict:
    """
    Calculate writing metrics (legacy interface for backward compatibility).

    Attempts to load from story_graph.json first, falls back to Twee parsing.

    Args:
        src_dir: Directory containing Twee files (or project root for story_graph.json)
        include: List of filename prefixes to include (ignored if using story_graph)
        exclude: List of filename prefixes to exclude (ignored if using story_graph)
        top_n: Number of top passages to include

    Returns:
        Dict containing all metrics
    """
    # Try to load from story_graph.json first (core library artifacts)
    story_graph_path = src_dir.parent / 'lib' / 'artifacts' / 'story_graph.json'
    if story_graph_path.exists():
        print(f"Loading from core artifacts: {story_graph_path}", file=sys.stderr)
        with open(story_graph_path, 'r', encoding='utf-8') as f:
            story_graph = json.load(f)
        return calculate_metrics_from_story_graph(story_graph, top_n)

    # Fall back to parsing Twee files directly (legacy path)
    print(f"Core artifacts not found, falling back to Twee parsing", file=sys.stderr)

    # Find all .twee files
    all_files = sorted(src_dir.glob('*.twee'))

    # Apply filters
    filtered_files = filter_files(all_files, include or [], exclude or [])

    if not filtered_files:
        return {
            'error': 'No files found matching filters',
            'total_words': 0,
            'file_count': 0,
            'passage_count': 0,
        }

    # Parse all files
    twee_files = [TweeFile(f) for f in filtered_files]

    # Collect all passages
    all_passages = []
    for tf in twee_files:
        all_passages.extend(tf.passages)

    # Calculate statistics
    total_words = sum(tf.word_count for tf in twee_files)
    passage_word_counts = [p.word_count for p in all_passages]
    file_word_counts = [tf.word_count for tf in twee_files]

    passage_stats = calculate_statistics(passage_word_counts)
    file_stats = calculate_statistics(file_word_counts)

    passage_distribution = generate_distribution(passage_word_counts)
    file_distribution = generate_distribution(file_word_counts)

    # Find top N longest passages
    top_passages = sorted(all_passages, key=lambda p: p.word_count, reverse=True)[:top_n]

    return {
        'total_words': total_words,
        'file_count': len(twee_files),
        'passage_count': len(all_passages),
        'passage_stats': passage_stats,
        'file_stats': file_stats,
        'passage_distribution': passage_distribution,
        'file_distribution': file_distribution,
        'top_passages': [p.to_dict() for p in top_passages],
        'files': [tf.to_dict() for tf in twee_files],
    }


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def format_number(n: int) -> str:
    """Format number with thousand separators."""
    return f"{n:,}"


def format_text_output(metrics: Dict) -> str:
    """
    Format metrics as human-readable text for CLI.

    Args:
        metrics: Metrics dictionary

    Returns:
        Formatted text string
    """
    if 'error' in metrics:
        return f"Error: {metrics['error']}\n"

    lines = []
    lines.append("=== Writing Metrics & Statistics ===\n")

    # Summary
    lines.append("Word Count Summary:")
    lines.append(f"  Total Words:     {format_number(metrics['total_words'])}")
    lines.append(f"  Files Analyzed:  {metrics['file_count']}")
    lines.append(f"  Passages:        {metrics['passage_count']}")
    lines.append("")

    # Passage Statistics
    ps = metrics['passage_stats']
    lines.append("Passage Statistics:")
    lines.append(f"  Minimum:   {ps['min']} words")
    lines.append(f"  Mean:      {ps['mean']:.1f} words")
    lines.append(f"  Median:    {ps['median']:.1f} words")
    lines.append(f"  Maximum:   {ps['max']} words")
    lines.append("")

    # File Statistics
    fs = metrics['file_stats']
    lines.append("File Statistics:")
    lines.append(f"  Minimum:   {fs['min']} words")
    lines.append(f"  Mean:      {fs['mean']:.1f} words")
    lines.append(f"  Median:    {fs['median']:.1f} words")
    lines.append(f"  Maximum:   {fs['max']} words")
    lines.append("")

    # Passage Distribution
    lines.append("Passage Distribution:")
    for label in ["0-100", "101-300", "301-500", "501-1000", "1000+"]:
        count = metrics['passage_distribution'][label]
        lines.append(f"  {label:12} {count:3} passages")
    lines.append("")

    # File Distribution
    lines.append("File Distribution:")
    for label in ["0-100", "101-300", "301-500", "501-1000", "1000+"]:
        count = metrics['file_distribution'][label]
        lines.append(f"  {label:12} {count:3} files")
    lines.append("")

    # Top Passages
    lines.append(f"Top {len(metrics['top_passages'])} Longest Passages:")
    for i, passage in enumerate(metrics['top_passages'], 1):
        lines.append(f"  {i}. {passage['name']:40} {passage['word_count']:4} words")
    lines.append("")

    return '\n'.join(lines)


def format_json_output(metrics: Dict) -> str:
    """
    Format metrics as JSON for HTML generation.

    Args:
        metrics: Metrics dictionary

    Returns:
        JSON string
    """
    return json.dumps(metrics, indent=2)


# =============================================================================
# MAIN CLI
# =============================================================================

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='Calculate writing metrics for Twee source files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # All files
  %(prog)s --include KEB            # Only KEB files
  %(prog)s --exclude mansel         # Exclude mansel files
  %(prog)s --top 10                 # Show top 10 passages
  %(prog)s --json                   # Output JSON
        """
    )

    parser.add_argument(
        '--src',
        type=Path,
        default=Path('src'),
        help='Source directory containing Twee files (default: src)'
    )

    parser.add_argument(
        '--include',
        nargs='+',
        help='Include only files with these prefixes'
    )

    parser.add_argument(
        '--exclude',
        nargs='+',
        help='Exclude files with these prefixes'
    )

    parser.add_argument(
        '--top',
        type=int,
        default=5,
        help='Number of top passages to show (default: 5)'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output JSON instead of text'
    )

    args = parser.parse_args()

    # Check if src directory exists
    if not args.src.exists():
        print(f"Error: Source directory '{args.src}' does not exist", file=sys.stderr)
        sys.exit(1)

    # Calculate metrics
    metrics = calculate_metrics(
        args.src,
        include=args.include,
        exclude=args.exclude,
        top_n=args.top
    )

    # Output
    if args.json:
        print(format_json_output(metrics))
    else:
        print(format_text_output(metrics))


if __name__ == '__main__':
    main()
