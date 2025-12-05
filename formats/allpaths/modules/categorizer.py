#!/usr/bin/env python3
"""
AllPaths Categorizer Module (Stage 4)

Classifies paths as new/modified/unchanged using two-level categorization:
1. PRIMARY: Path Existence Test - Did this exact sequence exist in base branch?
2. SECONDARY: Content/Prose Test - What changed?

This implements the complete git-based two-level categorization logic.
"""

import re
import sys
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Optional

from lib.git_service import GitService
from modules.parser import build_graph
from modules.path_generator import generate_all_paths_dfs, calculate_path_hash


# =============================================================================
# TEXT PROCESSING UTILITIES
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


# =============================================================================
# GIT FILE OPERATIONS
# =============================================================================

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


# =============================================================================
# TWEE PARSING (for base branch reconstruction)
# =============================================================================

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
            end = matches[i + 1].start()
        else:
            end = len(twee_content)

        passage_text = twee_content[start:end].strip()
        passages[passage_name] = {'text': passage_text}

    return passages


# =============================================================================
# BASE BRANCH PATH RECONSTRUCTION
# =============================================================================

def calculate_route_hash(route: List[str]) -> str:
    """Calculate hash based ONLY on passage names (route structure), not content.

    This identifies the path structure independent of content changes.
    Two paths with the same sequence of passages will have the same route_hash
    even if the content in those passages has been edited.

    Used in categorization logic to determine if a path existed in the base branch
    by comparing route hashes.

    Args:
        route: List of passage names in order

    Returns:
        8-character hex hash based on route structure only
    """
    route_string = ' → '.join(route)
    return hashlib.md5(route_string.encode()).hexdigest()[:8]


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

    # Calculate route hashes for all base paths
    base_route_hashes = set()
    for path in base_paths:
        route_hash = calculate_route_hash(path)
        base_route_hashes.add(route_hash)

    print(f"[INFO] Calculated {len(base_route_hashes)} unique route hashes from base branch", file=sys.stderr)

    return base_route_hashes


# =============================================================================
# PATH CATEGORIZATION (TWO-LEVEL TEST)
# =============================================================================

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

    print(f"\n[INFO] ===== Categorization Complete =====", file=sys.stderr)
    print(f"[INFO] Total files checked: {total_files_checked}", file=sys.stderr)
    print(f"[INFO] Git lookups: {git_lookups_succeeded} succeeded, {git_lookups_failed} failed", file=sys.stderr)
    print(f"[INFO] Category breakdown:", file=sys.stderr)
    print(f"[INFO]   - NEW: {new_count} paths", file=sys.stderr)
    print(f"[INFO]   - MODIFIED: {modified_count} paths", file=sys.stderr)
    print(f"[INFO]   - UNCHANGED: {unchanged_count} paths", file=sys.stderr)

    return categories
