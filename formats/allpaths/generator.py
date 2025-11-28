#!/usr/bin/env python3
"""
AllPaths Story Format Generator
Generates all possible story paths using depth-first search for AI-based continuity checking.
"""

import os
import re
import sys
import json
import hashlib
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
from typing import Dict, List, Tuple, Set, Optional
from jinja2 import Environment, FileSystemLoader

from lib.git_service import GitService
from modules.parser import (
    TweeStoryParser,
    parse_story_html,
    parse_link,
    extract_links,
    build_graph,
)
from modules.path_generator import (
    generate_all_paths_dfs,
    calculate_path_hash,
    format_passage_text,
)
from modules.git_enricher import (
    build_passage_to_file_mapping,
    get_path_commit_date,
    get_path_creation_date,
)
from modules.output_generator import (
    format_date_for_display,
    generate_html_output,
    save_validation_cache,
    generate_outputs,
)


# =============================================================================
# PATH GENERATION
# =============================================================================
# Note: Path generation functions moved to modules/path_generator.py
# - generate_all_paths_dfs: DFS traversal algorithm
# - calculate_path_hash: Path ID generation
# - format_passage_text: Text formatting utilities

# =============================================================================
# HASHING AND FINGERPRINTING
# =============================================================================

def strip_links_from_text(text: str) -> str:
    """Remove all Twee link syntax from text, preserving only prose.

    Strips:
    - [[target]]
    - [[display->target]]
    - [[target<-display]]
    - :: passage markers (passage names/boundaries)

    Also normalizes whitespace to prevent link-count differences from
    affecting the fingerprint.

    This allows us to compare pure prose content without navigation changes
    affecting the fingerprint.

    Args:
        text: Passage text with potential links

    Returns:
        Text with all link syntax removed and whitespace normalized
    """
    # Remove all [[...]] patterns
    text = re.sub(r'\[\[([^\]]+)\]\]', '', text)

    # Remove passage markers (lines starting with ::)
    # These are structural metadata, not prose content
    text = re.sub(r'^::.*$', '', text, flags=re.MULTILINE)

    # Normalize whitespace: collapse multiple newlines/spaces to single ones
    # This prevents different numbers of links from creating different whitespace patterns
    text = re.sub(r'\n\n+', '\n\n', text)  # Collapse 3+ newlines to 2
    text = re.sub(r'  +', ' ', text)        # Collapse multiple spaces to 1

    return text.strip()  # Remove leading/trailing whitespace


def normalize_prose_for_comparison(text: str) -> str:
    """Aggressively normalize prose for split-resistant comparison.

    This normalization handles cases where passages are split/reorganized:
    - Collapses all whitespace (spaces, newlines, tabs) to single spaces
    - Strips leading/trailing whitespace

    This allows detecting that "First part. Second part." is the same as
    "First part." + "\n" + "Second part." when concatenated.

    Args:
        text: Prose text (already with links stripped)

    Returns:
        Normalized text with all whitespace collapsed
    """
    # Replace all whitespace (including newlines) with single space
    normalized = re.sub(r'\s+', ' ', text)
    return normalized.strip()


def calculate_route_hash(path: List[str]) -> str:
    """Calculate hash based ONLY on passage names (route structure), not content.

    This identifies the path structure independent of content changes.
    Two paths with the same sequence of passages will have the same route_hash
    even if the content in those passages has been edited.

    Used in categorization logic to determine if a path existed in the base branch
    by comparing route hashes.

    Args:
        path: List of passage names in order

    Returns:
        8-character hex hash based on route structure only
    """
    route_string = ' → '.join(path)
    return hashlib.md5(route_string.encode()).hexdigest()[:8]



def generate_passage_id_mapping(passages: Dict) -> Dict[str, str]:
    """
    Generate a stable mapping from passage names to random-looking hex IDs.

    This prevents the AI from being influenced by passage names like "Day 5 KEB"
    which might make it think there are timeline issues.

    Returns:
        Dict mapping passage name -> hex ID

    Implementation notes:
    - WHY: Passage names like "Day 5" or "Day 19" can confuse AI continuity checking
      by making it think the timeline is wrong when it's actually correct
    - Uses MD5 hash of passage name for stability (same name = same ID across builds)
    - 12-character IDs provide enough entropy to avoid collisions
    - Sorted by passage name to ensure deterministic output
    """
    mapping = {}
    for passage_name in sorted(passages.keys()):
        # Use hash of passage name for stable IDs across builds
        # MD5 is fine here (not security-critical, just need stable random-looking IDs)
        passage_hash = hashlib.md5(passage_name.encode()).hexdigest()[:12]
        mapping[passage_name] = passage_hash
    return mapping

def generate_path_text(path: List[str], passages: Dict, path_num: int,
                      total_paths: int, include_metadata: bool = True,
                      passage_id_mapping: Dict[str, str] = None) -> str:
    """
    Generate formatted text for a single path.

    Args:
        path: List of passage names in the path
        passages: Dict of all passages
        path_num: Path number (1-indexed)
        total_paths: Total number of paths
        include_metadata: Whether to include path metadata header
        passage_id_mapping: Optional mapping from passage names to random IDs
                           (used to prevent AI from interpreting passage names)

    Returns:
        Formatted text for the path
    """
    lines = []

    if include_metadata:
        lines.append("=" * 80)
        lines.append(f"PATH {path_num} of {total_paths}")
        lines.append("=" * 80)
        # Use IDs in route if mapping provided
        if passage_id_mapping:
            route_with_ids = ' → '.join([passage_id_mapping.get(p, p) for p in path])
            lines.append(f"Route: {route_with_ids}")
        else:
            lines.append(f"Route: {' → '.join(path)}")
        lines.append(f"Length: {len(path)} passages")
        lines.append(f"Path ID: {calculate_path_hash(path, passages)}")
        lines.append("=" * 80)
        lines.append("")

    for i, passage_name in enumerate(path):
        if passage_name not in passages:
            if include_metadata:
                # Use ID if mapping provided
                display_name = passage_id_mapping.get(passage_name, passage_name) if passage_id_mapping else passage_name
                lines.append(f"\n[PASSAGE: {display_name}]")
                lines.append("[Passage not found]")
                lines.append("")
            continue

        passage = passages[passage_name]

        # Only include passage headings if metadata is enabled
        if include_metadata:
            # Use random ID instead of passage name if mapping provided
            display_name = passage_id_mapping.get(passage_name, passage_name) if passage_id_mapping else passage_name
            lines.append(f"[PASSAGE: {display_name}]")
            lines.append("")

        # Determine the next passage in the path (if any) to filter links
        next_passage = path[i + 1] if i + 1 < len(path) else None

        # Add formatted passage text with only the selected link visible
        formatted_text = format_passage_text(passage['text'], next_passage)

# =============================================================================
# VALIDATION CACHE
# =============================================================================

        lines.append(formatted_text)
        lines.append("")

    return '\n'.join(lines)

def load_validation_cache(cache_file: Path) -> Dict:
    """Load previously validated paths from cache.

    Args:
        cache_file: Path to the validation cache JSON file

    Returns:
        Dict mapping path hash -> validation data, or empty dict if cache doesn't exist
    """
    if not cache_file.exists():
        return {}

    try:
        with open(cache_file, 'r') as f:
            return json.load(f)
    except:
        return {}

# Note: save_validation_cache moved to modules/output_generator.py

# =============================================================================
# FILE AND PASSAGE MAPPING
# =============================================================================
# Note: build_passage_to_file_mapping moved to modules/git_enricher.py

# =============================================================================
# GIT INTEGRATION
# =============================================================================
# Note: Git enrichment functions moved to modules/git_enricher.py:
# - get_file_commit_date
# - get_file_creation_date
# - get_path_commit_date
# - get_path_creation_date

def calculate_path_similarity(path1: List[str], path2: List[str]) -> float:
    """
    Calculate similarity between two paths based on shared passages.

    Args:
        path1: First path (list of passage names)
        path2: Second path (list of passage names)

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not path1 or not path2:
        return 0.0

    # Calculate overlap using Jaccard similarity
    set1 = set(path1)
    set2 = set(path2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return intersection / union if union > 0 else 0.0

def verify_base_ref_accessible(repo_root: Path, base_ref: str) -> bool:
    """Verify that the base_ref is accessible in the git repository.

    Args:
        repo_root: Path to git repository root
        base_ref: Git ref to verify (e.g., 'origin/main', 'HEAD')

    Returns:
        True if base_ref is accessible, False otherwise
    """
    git_service = GitService(repo_root)
    return git_service.verify_ref_accessible(base_ref)

def get_file_content_from_git(file_path: Path, repo_root: Path, base_ref: str = 'HEAD') -> Optional[str]:
    """Get file content from git at a specific ref.

    Args:
        file_path: Absolute path to the file
        repo_root: Path to git repository root
        base_ref: Git ref to compare against (default: HEAD). For PRs, use base branch like 'origin/main'

    Returns:
        File content from the specified ref, or None if file doesn't exist in git
    """
    git_service = GitService(repo_root)
    return git_service.get_file_content_at_ref(file_path, base_ref)

def analyze_file_changes(file_path: Path, repo_root: Path, old_content: Optional[str]) -> dict:
    """Analyze what kind of changes a file has compared to git content.

    This is the core comparison function that determines file change type.
    It takes pre-fetched git content to avoid redundant git calls.

    Args:
        file_path: Absolute path to the .twee file
        repo_root: Path to git repository root
        old_content: Content from git (None if file is new)

    Returns:
        Dict with keys:
        - 'is_new': True if file doesn't exist in git
        - 'has_prose_changes': True if prose content changed
        - 'has_any_changes': True if any content changed (prose, links, structure)
        - 'reason': Human-readable explanation of the categorization
        - 'error': Error message if file couldn't be read (None otherwise)
    """
    rel_path = file_path.relative_to(repo_root)
    result = {
        'is_new': False,
        'has_prose_changes': False,
        'has_any_changes': False,
        'reason': '',
        'error': None
    }

    # Check if file exists in git
    if old_content is None:
        result['is_new'] = True
        result['has_prose_changes'] = True
        result['has_any_changes'] = True
        result['reason'] = f"File '{rel_path}' is NEW (not found in git)"
        return result

    # Get current version from filesystem
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
    except Exception as e:
        result['has_prose_changes'] = True
        result['has_any_changes'] = True
        result['error'] = str(e)
        result['reason'] = f"File '{rel_path}' could not be read: {e}"
        return result

    # Compare raw content first (fastest check)
    if old_content == new_content:
        result['reason'] = f"File '{rel_path}' is UNCHANGED (identical content)"
        return result

    # File has some changes - check if prose changed or just links/structure
    result['has_any_changes'] = True

    # Strip links and normalize whitespace for prose comparison
    old_prose = normalize_prose_for_comparison(strip_links_from_text(old_content))
    new_prose = normalize_prose_for_comparison(strip_links_from_text(new_content))

    if old_prose != new_prose:
        result['has_prose_changes'] = True
        # Calculate how much prose changed for debugging
        old_len = len(old_prose)
        new_len = len(new_prose)
        result['reason'] = f"File '{rel_path}' has PROSE CHANGES (old: {old_len} chars, new: {new_len} chars)"
    else:
        result['reason'] = f"File '{rel_path}' has LINK/STRUCTURE changes only (prose unchanged)"

    return result


def file_has_prose_changes(file_path: Path, repo_root: Path, base_ref: str = 'HEAD') -> bool:
    """Check if a .twee file has prose changes vs just link/structure changes.

    Compares current file content against git base ref. If prose (with links stripped
    and whitespace normalized) is identical, returns False (no prose changes).

    This allows detecting that a passage split is just reorganization, not new content.

    Args:
        file_path: Absolute path to the .twee file
        repo_root: Path to git repository root
        base_ref: Git ref to compare against (default: HEAD). For PRs, use base branch like 'origin/main'

    Returns:
        True if file has prose changes, False if only links/structure changed
    """
    print(f"[DEBUG] Checking prose changes for: {file_path.relative_to(repo_root)}", file=sys.stderr)

    # Get old version from git
    old_content = get_file_content_from_git(file_path, repo_root, base_ref)
    if old_content is None:
        # File doesn't exist in git, it's new
        print(f"[DEBUG] File not found in git (new file) - has prose changes: True", file=sys.stderr)
        return True

    # Get current version
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read file {file_path}: {e}", file=sys.stderr)
        return True  # Can't read, assume changed

    # Strip links and normalize whitespace
    old_prose = normalize_prose_for_comparison(strip_links_from_text(old_content))
    new_prose = normalize_prose_for_comparison(strip_links_from_text(new_content))

    has_changes = old_prose != new_prose
    print(f"[DEBUG] Prose comparison result: {'CHANGED' if has_changes else 'UNCHANGED'}", file=sys.stderr)
    return has_changes


def file_has_any_changes(file_path: Path, repo_root: Path, base_ref: str = 'HEAD') -> bool:
    """Check if a .twee file has ANY changes (including links/structure).

    Compares current file content against git base ref. If any content changed
    (prose, links, or structure), returns True.

    Args:
        file_path: Absolute path to the .twee file
        repo_root: Path to git repository root
        base_ref: Git ref to compare against (default: HEAD). For PRs, use base branch like 'origin/main'

    Returns:
        True if file has any changes, False if completely unchanged
    """
    print(f"[DEBUG] Checking any changes for: {file_path.relative_to(repo_root)}", file=sys.stderr)

    # Get old version from git
    old_content = get_file_content_from_git(file_path, repo_root, base_ref)
    if old_content is None:
        # File doesn't exist in git, it's new
        print(f"[DEBUG] File not found in git (new file) - has changes: True", file=sys.stderr)
        return True

    # Get current version
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
    except Exception as e:

# =============================================================================
# TWEE PARSING
# =============================================================================

        print(f"[ERROR] Could not read file {file_path}: {e}", file=sys.stderr)
        return True  # Can't read, assume changed

    # Compare raw content (no stripping)
    has_changes = old_content != new_content
    print(f"[DEBUG] Raw content comparison result: {'CHANGED' if has_changes else 'UNCHANGED'}", file=sys.stderr)
    return has_changes

def parse_twee_content(twee_content: str) -> Dict[str, Dict]:
    """
    Parse twee file content and extract passages.

    Args:
        twee_content: Content of a twee file

    Returns:
        Dict mapping passage name -> {'text': passage_text}
    """
    passages = {}

    # Split by passage headers (:: PassageName)
    # Pattern matches :: followed by passage name, optionally with tags in brackets
    pattern = r'^::\s*(.+?)(?:\s*\[.*?\])?\s*$'

    # Find all passage starts
    matches = list(re.finditer(pattern, twee_content, re.MULTILINE))

    for i, match in enumerate(matches):
        passage_name = match.group(1).strip()
        start = match.end()

        # Content goes until next passage or end of file
        if i + 1 < len(matches):

# =============================================================================
# BASE BRANCH PATH ANALYSIS
# =============================================================================

            end = matches[i + 1].start()
        else:
            end = len(twee_content)

        passage_text = twee_content[start:end].strip()
        passages[passage_name] = {'text': passage_text}

    return passages

def build_paths_from_base_branch(repo_root: Path, source_dir: Path, base_ref: str) -> Set[str]:
    """
    Build all paths from base branch and return their route hashes.

    This implements the PRIMARY path existence test: Did this exact sequence
    of passages exist in the base branch?

    Args:
        repo_root: Repository root path
        source_dir: Source directory containing twee files (relative to repo_root)
        base_ref: Git ref for base branch

    Returns:
        Set of route hashes (passage sequences) that existed in base branch
    """
    print(f"\n[INFO] Building paths from base branch '{base_ref}'...", file=sys.stderr)

    # Get list of twee files from base branch
    result = subprocess.run(
        ['git', 'ls-tree', '-r', '--name-only', base_ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        print(f"[WARN] Could not list files in base branch '{base_ref}': {result.stderr}", file=sys.stderr)
        return set()

    # Filter to twee files in source directory
    all_files = result.stdout.strip().split('\n')
    source_dir_str = str(source_dir.relative_to(repo_root))
    twee_files = [f for f in all_files if f.startswith(source_dir_str) and f.endswith('.twee')]

    print(f"[INFO] Found {len(twee_files)} twee files in base branch", file=sys.stderr)

    # Parse all twee files to build passages
    base_passages = {}

    for twee_file_rel in twee_files:
        # Get file content from base branch
        result = subprocess.run(
            ['git', 'show', f'{base_ref}:{twee_file_rel}'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print(f"[WARN] Could not read {twee_file_rel} from base branch", file=sys.stderr)
            continue

        # Parse twee content
        file_passages = parse_twee_content(result.stdout)
        base_passages.update(file_passages)

    print(f"[INFO] Parsed {len(base_passages)} passages from base branch", file=sys.stderr)

    # Build graph from base passages
    base_graph = build_graph(base_passages)

    # Find start passage
    start_passage = 'Start'
    if start_passage not in base_graph:
        # Try to find any passage that might be a start
        for name in base_passages.keys():
            if 'start' in name.lower():
                start_passage = name
                break

    if start_passage not in base_graph:
        print(f"[WARN] Start passage not found in base branch, cannot build paths", file=sys.stderr)
        return set()

    print(f"[INFO] Building all paths from '{start_passage}'...", file=sys.stderr)

    # Generate all paths from base branch
    base_paths = generate_all_paths_dfs(base_graph, start_passage)

    print(f"[INFO] Generated {len(base_paths)} paths from base branch", file=sys.stderr)


# =============================================================================
# PATH CATEGORIZATION
# =============================================================================

    # Calculate route hashes for all base paths
    base_route_hashes = set()
    for path in base_paths:
        route_hash = calculate_route_hash(path)
        base_route_hashes.add(route_hash)

    print(f"[INFO] Calculated {len(base_route_hashes)} unique route hashes from base branch", file=sys.stderr)

    return base_route_hashes

def categorize_paths(current_paths: List[List[str]], passages: Dict[str, Dict],
                    validation_cache: Dict,
                    passage_to_file: Dict[str, Path] = None,
                    repo_root: Path = None,
                    base_ref: str = 'HEAD') -> Dict[str, str]:
    """
    Categorize paths as New, Modified, or Unchanged using TWO-LEVEL test.

    The Two-Level Test (from spec):
    1. PRIMARY: Path Existence Test - Did this exact sequence of passages exist in the base branch?
       - If YES → Path is either MODIFIED or UNCHANGED (never NEW)
       - If NO → Path is either NEW or MODIFIED (depends on prose novelty)

    2. SECONDARY: Content/Prose Test - What changed?
       - If path existed: Did any passage content change? → MODIFIED or UNCHANGED
       - If path is new: Does it contain novel prose? → NEW or MODIFIED

    Args:
        current_paths: List of current paths
        passages: Dict of passage data
        validation_cache: Previous validation cache (not used for categorization)
        passage_to_file: Mapping from passage names to source file paths (optional)
        repo_root: Path to git repository root (optional)
        base_ref: Git ref to compare against (default: HEAD). For PRs, use base branch like 'origin/main'

    Returns:
        Dict mapping path hash -> category ('new', 'modified', 'unchanged')

    Algorithm:
        For each path:
            1. PRIMARY: Check if route hash (passage sequence) existed in base branch
            2. SECONDARY: For each file in path:
               - Check if prose content changed (git diff with links stripped)
               - Check if any content changed (including links)
            3. Categorize using two-level logic:
               - If path existed in base:
                 - Any file has content changes → MODIFIED
                 - No changes → UNCHANGED
               - If path is new (didn't exist in base):
                 - Any file has new prose → NEW
                 - Only link/structure changes → MODIFIED
               - If git unavailable → NEW (fallback)
    """
    print(f"\n[INFO] ===== Starting Path Categorization =====", file=sys.stderr)
    print(f"[INFO] Total paths to categorize: {len(current_paths)}", file=sys.stderr)
    print(f"[INFO] Base ref for comparison: {base_ref}", file=sys.stderr)

    categories = {}
    total_files_checked = 0
    git_lookups_succeeded = 0
    git_lookups_failed = 0

    # PRIMARY TEST: Build paths from base branch to check path existence
    base_route_hashes = set()
    if passage_to_file and repo_root:
        # Determine source directory from passage_to_file mapping
        # Get any file path and work backward to find src directory
        if passage_to_file:
            sample_file = next(iter(passage_to_file.values()))
            # Assume source dir is the parent of twee files (usually 'src')
            source_dir = sample_file.parent
            base_route_hashes = build_paths_from_base_branch(repo_root, source_dir, base_ref)
        else:
            print(f"[WARN] No passage_to_file mapping available, skipping PRIMARY test", file=sys.stderr)
    else:
        print(f"[WARN] No git data available, skipping PRIMARY test", file=sys.stderr)

    print(f"[INFO] Base branch has {len(base_route_hashes)} unique path routes", file=sys.stderr)

    for path in current_paths:
        path_hash = calculate_path_hash(path, passages)

        # Require git integration for accurate categorization
        if not passage_to_file or not repo_root:
            # No git data available - mark as new (conservative fallback)
            print(f"[WARN] No git data available for path {path_hash}, marking as 'new'", file=sys.stderr)
            categories[path_hash] = 'new'
            continue

        # Collect unique files for this path
        files_in_path = set()
        for passage_name in path:
            if passage_name in passage_to_file:
                files_in_path.add(passage_to_file[passage_name])

        print(f"\n[INFO] Categorizing path {path_hash} ({len(files_in_path)} files)", file=sys.stderr)

        # Check each file for changes (single git call per file)
        has_prose_changes = False
        has_any_changes = False
        files_checked_for_path = 0
        git_success_for_path = 0
        git_fail_for_path = 0
        file_reasons = []  # Collect reasons for detailed logging

        for file_path in files_in_path:
            files_checked_for_path += 1
            total_files_checked += 1

            # Single git call per file - fetch content once
            git_content = get_file_content_from_git(file_path, repo_root, base_ref)
            if git_content is not None:
                git_success_for_path += 1
                git_lookups_succeeded += 1
            else:
                git_fail_for_path += 1
                git_lookups_failed += 1

            # Analyze changes using pre-fetched git content (no redundant git calls)
            analysis = analyze_file_changes(file_path, repo_root, git_content)
            file_reasons.append(analysis['reason'])
            print(f"[DEBUG] {analysis['reason']}", file=sys.stderr)

            if analysis['error']:
                print(f"[ERROR] {analysis['error']}", file=sys.stderr)

            if analysis['has_prose_changes']:
                has_prose_changes = True
                # Continue checking remaining files for complete logging

            if analysis['has_any_changes']:
                has_any_changes = True

        # Log all file reasons for this path
        print(f"[INFO] Files in path {path_hash}:", file=sys.stderr)
        for reason in file_reasons:
            print(f"[INFO]   - {reason}", file=sys.stderr)

        # TWO-LEVEL CATEGORIZATION
        # PRIMARY: Check if this path existed in base branch
        route_hash = calculate_route_hash(path)
        path_existed_in_base = route_hash in base_route_hashes

        print(f"[INFO] Route hash: {route_hash}, existed in base: {path_existed_in_base}", file=sys.stderr)

        # SECONDARY: Apply logic based on path existence
        if path_existed_in_base:
            # Path existed in base → can only be MODIFIED or UNCHANGED (never NEW)
            if has_any_changes:
                categories[path_hash] = 'modified'
                print(f"[INFO] Path {path_hash}: MODIFIED (existed in base, has changes)", file=sys.stderr)
            else:
                categories[path_hash] = 'unchanged'
                print(f"[INFO] Path {path_hash}: UNCHANGED (existed in base, no changes)", file=sys.stderr)
        else:
            # Path is new (didn't exist in base) → NEW or MODIFIED based on prose
            if has_prose_changes:
                categories[path_hash] = 'new'
                print(f"[INFO] Path {path_hash}: NEW (new path with novel prose)", file=sys.stderr)
            else:
                # New path but no novel prose (e.g., passages moved/reorganized)
                categories[path_hash] = 'modified'
                print(f"[INFO] Path {path_hash}: MODIFIED (new path but no novel prose)", file=sys.stderr)

        print(f"[INFO] Git lookups for this path: {git_success_for_path} succeeded, {git_fail_for_path} failed", file=sys.stderr)

    # Summary statistics
    new_count = sum(1 for c in categories.values() if c == 'new')
    modified_count = sum(1 for c in categories.values() if c == 'modified')
    unchanged_count = sum(1 for c in categories.values() if c == 'unchanged')

# =============================================================================
# OUTPUT GENERATION
# =============================================================================


    print(f"\n[INFO] ===== Categorization Complete =====", file=sys.stderr)
    print(f"[INFO] Total files checked: {total_files_checked}", file=sys.stderr)
    print(f"[INFO] Git lookups: {git_lookups_succeeded} succeeded, {git_lookups_failed} failed", file=sys.stderr)
    print(f"[INFO] Category breakdown:", file=sys.stderr)
    print(f"[INFO]   - NEW: {new_count} paths", file=sys.stderr)
    print(f"[INFO]   - MODIFIED: {modified_count} paths", file=sys.stderr)
    print(f"[INFO]   - UNCHANGED: {unchanged_count} paths", file=sys.stderr)

    return categories

# =============================================================================
# OUTPUT GENERATION
# =============================================================================
# Note: Output generation functions moved to modules/output_generator.py
# - format_date_for_display
# - generate_html_output
# - save_validation_cache
# - generate_outputs

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> None:
    """Main entry point for AllPaths generator.

    Implements a 3-stage pipeline:
    - Stage 1: Parse HTML into story graph
    - Stages 2-4: Core processing (path generation, git enrichment, categorization)
    - Stage 5: Output generation (HTML, text files, cache)

    Usage:
        generator.py <input.html> [output_dir] [--write-intermediate]

    Args:
        input.html: Path to Tweego-compiled HTML file
        output_dir: Optional directory for output files (default: current directory)
        --write-intermediate: Optional flag to write intermediate artifacts for debugging

    Outputs:
        - allpaths.html: Interactive HTML viewer with all paths
        - allpaths-clean/*.txt: Individual path files with clean prose
        - allpaths-metadata/*.txt: Individual path files with metadata
        - allpaths-passage-mapping.json: Mapping between passage names and IDs
        - allpaths-validation-status.json: Cache of path validation data
        - dist/allpaths-intermediate/story_graph.json: Intermediate artifact (if --write-intermediate)
    """
    # =========================================================================
    # SETUP AND ARGUMENT PARSING
    # =========================================================================
    parser = argparse.ArgumentParser(
        description='AllPaths Story Format Generator - Generate all possible story paths for AI continuity checking'
    )
    parser.add_argument('input_file', type=Path, help='Path to Tweego-compiled HTML file')
    parser.add_argument('output_dir', type=Path, nargs='?', default=Path('.'),
                       help='Directory for output files (default: current directory)')
    parser.add_argument('--write-intermediate', action='store_true', default=False,
                       help='Write intermediate artifacts to dist/allpaths-intermediate/ for debugging')

    args = parser.parse_args()

    input_file = args.input_file
    output_dir = args.output_dir
    write_intermediate = args.write_intermediate

    # Read input HTML
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # =========================================================================
    # STAGE 1: PARSE
    # =========================================================================
    print("\n" + "="*80, file=sys.stderr)
    print("STAGE 1: PARSE - Extracting story structure from HTML", file=sys.stderr)
    print("="*80, file=sys.stderr)

    # Parse story structure from HTML
    story_data, passages = parse_story_html(html_content)
    print(f"Extracted {len(passages)} passages from story '{story_data['name']}'", file=sys.stderr)

    # Build graph representation
    graph = build_graph(passages)
    print(f"Built story graph with {len(graph)} nodes", file=sys.stderr)

    # Find start passage
    start_passage = None
    for name, passage in passages.items():
        if passage['pid'] == story_data['start']:
            start_passage = name
            break

    if not start_passage:
        start_passage = 'Start'

    print(f"Start passage: {start_passage}", file=sys.stderr)

    # Write intermediate artifact if requested
    if write_intermediate:
        intermediate_dir = output_dir / 'allpaths-intermediate'
        intermediate_dir.mkdir(parents=True, exist_ok=True)

        story_graph = {
            'passages': {
                name: {
                    'text': passage['text'],
                    'pid': passage['pid'],
                    'links': graph.get(name, [])
                }
                for name, passage in passages.items()
            },
            'start_passage': start_passage,
            'metadata': {
                'story_title': story_data['name'],
                'ifid': story_data.get('ifid', ''),
                'format': story_data.get('format', 'Twine'),
                'format_version': story_data.get('format-version', '')
            }
        }

        story_graph_file = intermediate_dir / 'story_graph.json'
        with open(story_graph_file, 'w', encoding='utf-8') as f:
            json.dump(story_graph, f, indent=2)

        print(f"[DEBUG] Wrote intermediate artifact: {story_graph_file}", file=sys.stderr)

    # =========================================================================
    # STAGE 2: PATH GENERATION
    # =========================================================================
    print("\n" + "="*80, file=sys.stderr)
    print("STAGE 2: PATH GENERATION - Computing all possible story paths", file=sys.stderr)
    print("="*80, file=sys.stderr)

    # Generate all paths using depth-first search
    all_paths = generate_all_paths_dfs(graph, start_passage)
    print(f"Generated {len(all_paths)} total paths", file=sys.stderr)
    if all_paths:
        path_lengths = [len(p) for p in all_paths]
        print(f"Path length range: {min(path_lengths)}-{max(path_lengths)} passages", file=sys.stderr)

    # =========================================================================
    # STAGE 3: GIT ENRICHMENT
    # =========================================================================
    print("\n" + "="*80, file=sys.stderr)
    print("STAGE 3: GIT ENRICHMENT - Adding version control metadata", file=sys.stderr)
    print("="*80, file=sys.stderr)

    # Build passage-to-file mapping for git commit date tracking
    repo_root = output_dir.parent  # Assume output_dir is dist/ and repo root is parent
    source_dir = repo_root / 'src'
    passage_to_file = build_passage_to_file_mapping(source_dir)
    print(f"Mapped {len(passage_to_file)} passages to source files", file=sys.stderr)

    # Generate passage ID mapping (random hex IDs to prevent AI from interpreting passage names)
    passage_id_mapping = generate_passage_id_mapping(passages)

    # Save the mapping for later translation back to passage names
    mapping_file = output_dir / 'allpaths-passage-mapping.json'
    with open(mapping_file, 'w', encoding='utf-8') as f:
        # Also include reverse mapping for easy lookup
        reverse_mapping = {v: k for k, v in passage_id_mapping.items()}
        json.dump({
            'name_to_id': passage_id_mapping,
            'id_to_name': reverse_mapping
        }, f, indent=2)

    print(f"Generated passage ID mapping: {mapping_file}", file=sys.stderr)

    # Load validation cache (stored at repository root, not in dist/)
    cache_file = output_dir.parent / 'allpaths-validation-status.json'
    validation_cache = load_validation_cache(cache_file)
    print(f"Loaded validation cache with {len(validation_cache)} entries", file=sys.stderr)

    # Determine git base ref for comparison
    # In PR context (GitHub Actions), compare against base branch
    # In local context, compare against HEAD (for uncommitted changes)
    base_ref = os.getenv('GITHUB_BASE_REF')
    if base_ref:
        # GitHub Actions PR context - use origin/base_branch
        base_ref = f'origin/{base_ref}'
        print(f"Using git base ref: {base_ref} (from GITHUB_BASE_REF)", file=sys.stderr)
    else:
        # Local context - use HEAD to detect uncommitted changes
        base_ref = 'HEAD'
        print(f"Using git base ref: {base_ref} (local development)", file=sys.stderr)

    # Verify that the base ref is accessible before proceeding
    if not verify_base_ref_accessible(repo_root, base_ref):
        print(f"[ERROR] Cannot access base ref '{base_ref}' - path categorization will be incorrect!", file=sys.stderr)
        print(f"[ERROR] All paths will be marked as 'new' instead of properly categorized.", file=sys.stderr)
        # Continue execution but warn user that results will be incorrect

    # =========================================================================
    # STAGE 4: PATH CATEGORIZATION
    # =========================================================================
    print("\n" + "="*80, file=sys.stderr)
    print("STAGE 4: PATH CATEGORIZATION - Classifying paths (new/modified/unchanged)", file=sys.stderr)
    print("="*80, file=sys.stderr)

    # Categorize paths using two-level test (path existence + content changes)
    path_categories = categorize_paths(all_paths, passages, validation_cache,
                                      passage_to_file, repo_root, base_ref)

    new_count = sum(1 for c in path_categories.values() if c == 'new')
    modified_count = sum(1 for c in path_categories.values() if c == 'modified')
    unchanged_count = sum(1 for c in path_categories.values() if c == 'unchanged')

    print(f"\nCategorization summary:", file=sys.stderr)
    print(f"  NEW: {new_count} paths", file=sys.stderr)
    print(f"  MODIFIED: {modified_count} paths", file=sys.stderr)
    print(f"  UNCHANGED: {unchanged_count} paths", file=sys.stderr)

    # Update validation cache with current paths BEFORE generating outputs
    # This ensures outputs have access to fresh dates and categories
    for path in all_paths:
        path_hash = calculate_path_hash(path, passages)
        commit_date = get_path_commit_date(path, passage_to_file, repo_root)
        creation_date = get_path_creation_date(path, passage_to_file, repo_root)
        category = path_categories.get(path_hash, 'new')

        if path_hash not in validation_cache:
            validation_cache[path_hash] = {
                'route': ' → '.join(path),
                'first_seen': datetime.now().isoformat(),
                'validated': False,
                'commit_date': commit_date,
                'created_date': creation_date,
                'category': category,
            }
        else:
            # Update commit date, created date, and category for existing entries
            validation_cache[path_hash]['commit_date'] = commit_date

            # Update created_date to reflect the earliest passage creation date
            # This ensures we show when content was first created, not when path structure appeared
            if creation_date:
                validation_cache[path_hash]['created_date'] = creation_date

            # Always update category - it's computed fresh from git on each build
            validation_cache[path_hash]['category'] = category

    print(f"Updated validation cache with {len(validation_cache)} total entries", file=sys.stderr)

    # =========================================================================
    # STAGE 5: OUTPUT GENERATION
    # =========================================================================
    print("\n" + "="*80, file=sys.stderr)
    print("STAGE 5: OUTPUT GENERATION - Creating HTML viewer and text files", file=sys.stderr)
    print("="*80, file=sys.stderr)

    # Generate all outputs using the output_generator module
    result = generate_outputs(
        story_data=story_data,
        passages=passages,
        all_paths=all_paths,
        output_dir=output_dir,
        validation_cache=validation_cache,
        path_categories=path_categories,
        passage_id_mapping=passage_id_mapping,
        cache_file=cache_file
    )

    # Extract file paths from result for summary
    html_file = Path(result['html_file'])
    text_dir = Path(result['text_dir'])
    continuity_dir = Path(result['metadata_dir'])

    print(f"\nGenerated outputs:", file=sys.stderr)
    print(f"  HTML viewer: {html_file}", file=sys.stderr)
    print(f"  Text files (clean): {text_dir}/ ({len(all_paths)} files)", file=sys.stderr)
    print(f"  Text files (metadata): {continuity_dir}/ ({len(all_paths)} files)", file=sys.stderr)
    print(f"  Passage mapping: {mapping_file}", file=sys.stderr)
    print(f"  Validation cache: {cache_file}", file=sys.stderr)

    # =========================================================================
    # PIPELINE COMPLETE
    # =========================================================================
    print("\n" + "="*80, file=sys.stderr)
    print("=== ALLPATHS GENERATION COMPLETE ===", file=sys.stderr)
    print("="*80, file=sys.stderr)
    print(f"Story: {story_data['name']}", file=sys.stderr)
    print(f"Total paths: {len(all_paths)}", file=sys.stderr)
    if all_paths:
        print(f"Path lengths: {min(len(p) for p in all_paths)}-{max(len(p) for p in all_paths)} passages", file=sys.stderr)
    print(f"HTML output: {html_file}", file=sys.stderr)
    print("="*80 + "\n", file=sys.stderr)

if __name__ == '__main__':
    main()
