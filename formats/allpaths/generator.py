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
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
from typing import Dict, List, Tuple, Set, Optional

class TweeStoryParser(HTMLParser):
    """Parse Tweego-compiled HTML to extract story data"""

    def __init__(self):
        super().__init__()
        self.story_data = {}
        self.passages = {}
        self.current_passage = None
        self.current_data = []
        self.in_passage = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'tw-storydata':
            self.story_data = {
                'name': attrs_dict.get('name', 'Untitled'),
                'ifid': attrs_dict.get('ifid', ''),
                'start': attrs_dict.get('startnode', '1'),
            }
        elif tag == 'tw-passagedata':
            self.in_passage = True
            self.current_passage = {
                'pid': attrs_dict.get('pid', ''),
                'name': attrs_dict.get('name', ''),
                'tags': attrs_dict.get('tags', '').split() if attrs_dict.get('tags') else [],
                'text': '',
            }
            self.current_data = []

    def handle_endtag(self, tag):
        if tag == 'tw-passagedata' and self.in_passage:
            self.current_passage['text'] = ''.join(self.current_data).strip()
            self.passages[self.current_passage['name']] = self.current_passage
            self.in_passage = False
            self.current_passage = None
            self.current_data = []

    def handle_data(self, data):
        if self.in_passage:
            self.current_data.append(data)

def parse_story_html(html_content: str) -> Tuple[Dict, Dict]:
    """Parse Tweego-compiled HTML and extract story data and passages"""
    parser = TweeStoryParser()
    parser.feed(html_content)
    return parser.story_data, parser.passages

def parse_link(link_text: str) -> str:
    """Parse a Twee link and extract the target passage name"""
    # [[target]]
    # [[display->target]]
    # [[target<-display]]
    if '->' in link_text:
        return link_text.split('->')[1].strip()
    elif '<-' in link_text:
        return link_text.split('<-')[0].strip()
    else:
        return link_text.strip()

def extract_links(passage_text: str) -> List[str]:
    """Extract all link targets from passage text"""
    links = re.findall(r'\[\[([^\]]+)\]\]', passage_text)
    targets = [parse_link(link) for link in links]

    # Remove duplicates while preserving order
    seen = set()
    unique_targets = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            unique_targets.append(t)

    return unique_targets

def build_graph(passages: Dict) -> Dict[str, List[str]]:
    """Build a directed graph from passages"""
    graph = {}

    for name, passage in passages.items():
        # Skip special passages
        if name in ['StoryTitle', 'StoryData']:
            continue

        links = extract_links(passage['text'])
        graph[name] = links

    return graph

def generate_all_paths_dfs(graph: Dict[str, List[str]], start: str,
                          current_path: List[str] = None,
                          max_cycles: int = 1) -> List[List[str]]:
    """
    Generate all possible paths from start to end nodes using DFS.

    Args:
        graph: Adjacency list representation of story graph
        start: Starting passage name
        current_path: Current path being explored
        max_cycles: Maximum number of times a passage can be visited

    Returns:
        List of paths, where each path is a list of passage names
    """
    if current_path is None:
        current_path = []

    # Add current node to path
    current_path = current_path + [start]

    # Check for excessive cycles
    if current_path.count(start) > max_cycles:
        # Found a cycle, terminate this path
        return []

    # Base case: end node (no outgoing links)
    if start not in graph or not graph[start]:
        return [current_path]

    # Recursive case: explore all branches
    all_paths = []
    for target in graph[start]:
        paths_from_target = generate_all_paths_dfs(graph, target, current_path, max_cycles)
        all_paths.extend(paths_from_target)

    return all_paths

def format_passage_text(text: str, selected_target: str = None) -> str:
    """
    Format passage text for reading (convert links to plain text).

    Args:
        text: The passage text to format
        selected_target: If provided, only show this link and mark others as [unselected] if multiple links exist

    Returns:
        Formatted text with links converted to visible text
    """
    # Replace [[display->target]] with "display"
    # Replace [[target<-display]] with "display"
    # Replace [[target]] with "target"

    # Count total links to determine if we should use placeholders
    link_count = len(re.findall(r'\[\[([^\]]+)\]\]', text))
    use_placeholder = link_count > 1

    def replace_link(match):
        link = match.group(1)

        # Extract display text and target
        if '->' in link:
            display = link.split('->')[0].strip()
            target = link.split('->')[1].strip()
        elif '<-' in link:
            display = link.split('<-')[1].strip()
            target = link.split('<-')[0].strip()
        else:
            display = link.strip()
            target = link.strip()

        # If we have a selected target, only show that one
        if selected_target is not None:
            if target == selected_target:
                return display
            else:
                # Use placeholder if multiple links exist, otherwise remove completely
                return "[unselected]" if use_placeholder else ""
        else:
            return display

    return re.sub(r'\[\[([^\]]+)\]\]', replace_link, text)

def calculate_path_hash(path: List[str], passages: Dict[str, Dict]) -> str:
    """Calculate hash based on path route AND passage content.

    This ensures the hash changes when:
    - Passage names change (route structure)
    - Passage content is edited (text changes)
    - Path structure changes (added/removed passages)

    Args:
        path: List of passage names in order
        passages: Dict of passage data including text content

    Returns:
        8-character hex hash
    """
    content_parts = []
    for passage_name in path:
        if passage_name in passages:
            # Include both structure and content in hash
            passage_text = passages[passage_name].get('text', '')
            content_parts.append(f"{passage_name}:{passage_text}")
        else:
            # Passage doesn't exist (shouldn't happen, but be defensive)
            content_parts.append(f"{passage_name}:MISSING")

    combined = '\n'.join(content_parts)
    return hashlib.md5(combined.encode()).hexdigest()[:8]

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

def calculate_raw_content_fingerprint(path: List[str], passages: Dict[str, Dict]) -> str:
    """Calculate fingerprint based on raw passage content INCLUDING links.

    DEPRECATED: No longer used for categorization (git-first approach).
    Kept for backward compatibility with tests and old cache files.

    This detects ANY content change (prose OR links).

    Args:
        path: List of passage names in order
        passages: Dict of passage data including text content

    Returns:
        8-character hex hash based on full content (with links)
    """
    content_parts = []
    for passage_name in path:
        if passage_name in passages:
            passage_text = passages[passage_name].get('text', '')
            content_parts.append(passage_text)
        else:
            content_parts.append("MISSING")

    combined = '\n'.join(content_parts)
    return hashlib.md5(combined.encode()).hexdigest()[:8]

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

def calculate_content_fingerprint(path: List[str], passages: Dict[str, Dict]) -> str:
    """Calculate fingerprint based ONLY on prose content, not names or links.

    DEPRECATED: No longer used for categorization (git-first approach).
    Kept for backward compatibility with tests and old cache files.

    This fingerprint:
    - Strips link syntax ([[...]]) to focus on prose changes
    - Ignores passage names
    - Ignores route structure
    - Normalizes whitespace aggressively to detect splits/reorganizations

    This means:
    - Adding/removing/changing links → No fingerprint change
    - Adding/editing prose → Fingerprint changes
    - Restructuring/splitting passages → No fingerprint change (if prose is same)

    Args:
        path: List of passage names in order
        passages: Dict of passage data including text content

    Returns:
        8-character hex hash based on prose content only
    """
    content_parts = []
    for passage_name in path:
        if passage_name in passages:
            # Strip links to get prose-only content
            passage_text = passages[passage_name].get('text', '')
            prose_only = strip_links_from_text(passage_text)
            content_parts.append(prose_only)
        else:
            # Passage doesn't exist (shouldn't happen, but be defensive)
            content_parts.append("MISSING")

    # Join all prose and normalize aggressively to handle splits
    combined = ' '.join(content_parts)
    normalized = normalize_prose_for_comparison(combined)
    return hashlib.md5(normalized.encode()).hexdigest()[:8]

def calculate_route_hash(path: List[str]) -> str:
    """Calculate hash based ONLY on passage names (route structure), not content.

    DEPRECATED: No longer used for categorization (git-first approach).
    Kept for backward compatibility with tests and old cache files.

    This identifies the path structure independent of content changes.
    Two paths with the same sequence of passages will have the same route_hash
    even if the content in those passages has been edited.

    Args:
        path: List of passage names in order

    Returns:
        8-character hex hash based on route structure only
    """
    route_string = ' → '.join(path)
    return hashlib.md5(route_string.encode()).hexdigest()[:8]

def calculate_passage_prose_fingerprint(passage_text: str) -> str:
    """Calculate fingerprint for a single passage's prose content (no links).

    DEPRECATED: No longer used for categorization (git-first approach).
    Kept for backward compatibility with tests and old cache files.

    This allows detecting when prose content is reused/split across passages.
    For example, if passage A is split into A1 and A2, we can detect that
    the prose in A1 and A2 existed before in A.

    Args:
        passage_text: The text content of a single passage

    Returns:
        8-character hex hash based on prose-only content
    """
    prose_only = strip_links_from_text(passage_text)
    return hashlib.md5(prose_only.encode()).hexdigest()[:8]

def build_passage_fingerprints(path: List[str], passages: Dict[str, Dict]) -> Dict[str, str]:
    """Build a mapping of passage names to their prose fingerprints for a path.

    DEPRECATED: No longer used for categorization (git-first approach).
    Kept for backward compatibility with tests and old cache files.

    Args:
        path: List of passage names in the path
        passages: Dict of all passages

    Returns:
        Dict mapping passage name -> prose fingerprint
    """
    fingerprints = {}
    for passage_name in path:
        if passage_name in passages:
            passage_text = passages[passage_name].get('text', '')
            fingerprints[passage_name] = calculate_passage_prose_fingerprint(passage_text)
        else:
            fingerprints[passage_name] = 'MISSING'
    return fingerprints

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
        lines.append(formatted_text)
        lines.append("")

    return '\n'.join(lines)

def load_validation_cache(cache_file: Path) -> Dict:
    """Load previously validated paths from cache"""
    if not cache_file.exists():
        return {}

    try:
        with open(cache_file, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_validation_cache(cache_file: Path, cache: Dict):
    """Save validated paths to cache"""
    with open(cache_file, 'w') as f:
        json.dump(cache, indent=2, fp=f)

def build_passage_to_file_mapping(source_dir: Path) -> Dict[str, Path]:
    """
    Build a mapping from passage names to their source .twee files.

    Args:
        source_dir: Directory containing .twee source files

    Returns:
        Dict mapping passage name -> file path
    """
    mapping = {}

    # Find all .twee files
    for twee_file in source_dir.glob('**/*.twee'):
        try:
            with open(twee_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all passage declarations (:: PassageName)
            passages_in_file = re.findall(r'^:: (.+?)(?:\s*\[.*?\])?\s*$', content, re.MULTILINE)

            for passage_name in passages_in_file:
                mapping[passage_name.strip()] = twee_file
        except Exception as e:
            # Skip files that can't be read
            print(f"Warning: Could not read {twee_file}: {e}", file=sys.stderr)
            continue

    return mapping

def get_file_commit_date(file_path: Path, repo_root: Path) -> Optional[str]:
    """
    Get the most recent commit date for a file using git log.

    Args:
        file_path: Path to the file
        repo_root: Path to git repository root

    Returns:
        ISO format datetime string of most recent commit, or None if unavailable

    Implementation notes:
    - Uses -m flag to include merge commits (important for PR-based workflows)
    - Returns author date (%aI) not committer date for consistency
    - 5-second timeout prevents hangs on large repos
    """
    try:
        # Get the most recent commit date for this file
        # -m: Include merge commits (without this, merge commits are skipped)
        # -1: Only get the most recent commit
        # --format=%aI: ISO 8601 author date format
        result = subprocess.run(
            ['git', 'log', '-m', '-1', '--format=%aI', '--', str(file_path)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            return None
    except Exception as e:
        print(f"Warning: Could not get commit date for {file_path}: {e}", file=sys.stderr)
        return None

def get_file_creation_date(file_path: Path, repo_root: Path) -> Optional[str]:
    """
    Get the earliest commit date for a file (when it was first added).

    Args:
        file_path: Path to the file
        repo_root: Path to git repository root

    Returns:
        ISO format datetime string of earliest commit, or None if unavailable
    """
    try:
        # Get all commit dates in reverse chronological order, with -m to include merge commits
        result = subprocess.run(
            ['git', 'log', '-m', '--format=%aI', '--reverse', '--', str(file_path)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            dates = result.stdout.strip().split('\n')
            return dates[0] if dates else None
        else:
            return None
    except Exception as e:
        print(f"Warning: Could not get creation date for {file_path}: {e}", file=sys.stderr)
        return None

def get_path_commit_date(path: List[str], passage_to_file: Dict[str, Path],
                        repo_root: Path) -> Optional[str]:
    """
    Get the most recent commit date among all passages in a path.

    Args:
        path: List of passage names in the path
        passage_to_file: Mapping from passage names to file paths
        repo_root: Path to git repository root

    Returns:
        ISO format datetime string of most recent commit, or None if unavailable
    """
    commit_dates = []

    for passage_name in path:
        if passage_name not in passage_to_file:
            continue

        file_path = passage_to_file[passage_name]
        commit_date = get_file_commit_date(file_path, repo_root)

        if commit_date:
            commit_dates.append(commit_date)

    # Return the most recent date
    if commit_dates:
        return max(commit_dates)
    else:
        return None

def get_path_creation_date(path: List[str], passage_to_file: Dict[str, Path],
                          repo_root: Path) -> Optional[str]:
    """
    Get the date when a path became fully available (complete).
    This finds the most recent creation date among all passages in the path.

    Args:
        path: List of passage names in the path
        passage_to_file: Mapping from passage names to file paths
        repo_root: Path to git repository root

    Returns:
        ISO format datetime string of when path became complete, or None if unavailable
    """
    creation_dates = []

    for passage_name in path:
        if passage_name not in passage_to_file:
            continue

        file_path = passage_to_file[passage_name]
        creation_date = get_file_creation_date(file_path, repo_root)

        if creation_date:
            creation_dates.append(creation_date)

    # Return the most recent creation date - when the path became complete
    if creation_dates:
        return max(creation_dates)
    else:
        return None

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

def get_file_content_from_git(file_path: Path, repo_root: Path, base_ref: str = 'HEAD') -> Optional[str]:
    """Get file content from git at a specific ref.

    Args:
        file_path: Absolute path to the file
        repo_root: Path to git repository root
        base_ref: Git ref to compare against (default: HEAD). For PRs, use base branch like 'origin/main'

    Returns:
        File content from the specified ref, or None if file doesn't exist in git
    """
    try:
        rel_path = file_path.relative_to(repo_root)
        result = subprocess.run(
            ['git', 'show', f'{base_ref}:{rel_path}'],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout
        else:
            return None
    except Exception as e:
        print(f"Warning: Could not get git content for {file_path} at {base_ref}: {e}", file=sys.stderr)
        return None

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
    # Get old version from git
    old_content = get_file_content_from_git(file_path, repo_root, base_ref)
    if old_content is None:
        # File doesn't exist in git, it's new
        return True

    # Get current version
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
    except Exception as e:
        print(f"Warning: Could not read file {file_path}: {e}", file=sys.stderr)
        return True  # Can't read, assume changed

    # Strip links and normalize whitespace
    old_prose = normalize_prose_for_comparison(strip_links_from_text(old_content))
    new_prose = normalize_prose_for_comparison(strip_links_from_text(new_content))

    return old_prose != new_prose

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
    # Get old version from git
    old_content = get_file_content_from_git(file_path, repo_root, base_ref)
    if old_content is None:
        # File doesn't exist in git, it's new
        return True

    # Get current version
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
    except Exception as e:
        print(f"Warning: Could not read file {file_path}: {e}", file=sys.stderr)
        return True  # Can't read, assume changed

    # Compare raw content (no stripping)
    return old_content != new_content

def categorize_paths(current_paths: List[List[str]], passages: Dict[str, Dict],
                    validation_cache: Dict,
                    passage_to_file: Dict[str, Path] = None,
                    repo_root: Path = None,
                    base_ref: str = 'HEAD') -> Dict[str, str]:
    """
    Categorize paths as New, Modified, or Unchanged using git-based change detection.

    Uses git as the single source of truth for change detection:
    - NEW: Path contains at least one file with genuinely new prose content
    - MODIFIED: All files have same prose, but links/structure changed
    - UNCHANGED: No files changed at all (prose, links, structure all same)

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
            1. Get .twee files containing passages in this path
            2. For each file:
               - Check if prose content changed (git diff with links stripped)
               - Check if any content changed (including links)
            3. Categorize:
               - If any file has new prose → NEW
               - If any file has link-only changes → MODIFIED
               - If no files changed → UNCHANGED
               - If git unavailable → NEW (fallback)
    """
    categories = {}

    for path in current_paths:
        path_hash = calculate_path_hash(path, passages)

        # Require git integration for accurate categorization
        if not passage_to_file or not repo_root:
            # No git data available - mark as new (conservative fallback)
            categories[path_hash] = 'new'
            continue

        # Collect unique files for this path
        files_in_path = set()
        for passage_name in path:
            if passage_name in passage_to_file:
                files_in_path.add(passage_to_file[passage_name])

        # Check each file for changes
        has_prose_changes = False
        has_any_changes = False

        for file_path in files_in_path:
            if file_has_prose_changes(file_path, repo_root, base_ref):
                has_prose_changes = True
                break  # Early exit - found new prose

            if file_has_any_changes(file_path, repo_root, base_ref):
                has_any_changes = True
                # Don't break - still need to check other files for prose changes

        # Categorize based on what changed
        if has_prose_changes:
            categories[path_hash] = 'new'
        elif has_any_changes:
            categories[path_hash] = 'modified'
        else:
            categories[path_hash] = 'unchanged'

    return categories

def generate_html_output(story_data: Dict, passages: Dict, all_paths: List[List[str]],
                        validation_cache: Dict = None, path_categories: Dict[str, str] = None) -> str:
    """Generate HTML output with all paths"""
    if validation_cache is None:
        validation_cache = {}
    if path_categories is None:
        path_categories = {}

    # Calculate statistics
    path_lengths = [len(p) for p in all_paths]
    total_passages = sum(path_lengths)

    # Sort paths by creation date (newest first), then by category
    paths_with_metadata = []
    for path in all_paths:
        path_hash = calculate_path_hash(path, passages)
        created_date = validation_cache.get(path_hash, {}).get('created_date', '')
        category = path_categories.get(path_hash, 'new')
        paths_with_metadata.append((path, path_hash, created_date, category))

    # Sort: by category first (new, modified, unchanged), then newest creation date within each category
    # Use '0' as sentinel for missing dates - sorts before real ISO dates, ends up last with reverse=True
    category_order = {'new': 2, 'modified': 1, 'unchanged': 0}
    paths_with_metadata.sort(key=lambda x: (
        category_order.get(x[3], 3),  # category (new=2, modified=1, unchanged=0 - higher sorts first with reverse=True)
        x[2] if x[2] else '0',  # created_date (newest first within category, '0' sorts last)
    ), reverse=True)

    # Count paths by category
    new_count = sum(1 for _, _, _, cat in paths_with_metadata if cat == 'new')
    modified_count = sum(1 for _, _, _, cat in paths_with_metadata if cat == 'modified')
    unchanged_count = sum(1 for _, _, _, cat in paths_with_metadata if cat == 'unchanged')

    # Also count validation status
    validated_count = sum(1 for path in all_paths
                         if validation_cache.get(calculate_path_hash(path, passages), {}).get('validated', False))

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Paths - {story_data['name']}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}

        .header h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        .header .subtitle {{
            opacity: 0.9;
            font-size: 1rem;
        }}

        .stats {{
            background: white;
            margin: 2rem auto;
            max-width: 1200px;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}

        .stats h2 {{
            margin-bottom: 1rem;
            color: #667eea;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}

        .stat-item {{
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 4px;
            border-left: 4px solid #667eea;
        }}

        .stat-label {{
            font-size: 0.875rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .stat-value {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #333;
            margin-top: 0.25rem;
        }}

        .filter-section {{
            background: white;
            margin: 2rem auto;
            max-width: 1200px;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}

        .filter-buttons {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            padding: 0.5rem 1rem;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s;
        }}

        .filter-btn:hover {{
            background: #667eea;
            color: white;
        }}

        .filter-btn.active {{
            background: #667eea;
            color: white;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}

        .path {{
            background: white;
            margin-bottom: 2rem;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: box-shadow 0.3s;
        }}

        .path:hover {{
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}

        .path.new {{
            border-left: 5px solid #007bff;
        }}

        .path.modified {{
            border-left: 5px solid #ffc107;
        }}

        .path.unchanged {{
            border-left: 5px solid #28a745;
        }}

        .path-header {{
            background: #f8f9fa;
            padding: 1.5rem;
            border-bottom: 1px solid #e9ecef;
        }}

        .path-title {{
            font-size: 1.25rem;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 0.5rem;
        }}

        .path-meta {{
            display: flex;
            gap: 1.5rem;
            flex-wrap: wrap;
            font-size: 0.875rem;
            color: #666;
        }}

        .path-meta-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-new {{
            background: #007bff;
            color: white;
        }}

        .badge-modified {{
            background: #ffc107;
            color: #333;
        }}

        .badge-unchanged {{
            background: #28a745;
            color: white;
        }}

        .badge-validated {{
            background: #6f42c1;
            color: white;
        }}

        .route {{
            background: #e9ecef;
            padding: 1rem;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.875rem;
            overflow-x: auto;
            white-space: nowrap;
        }}

        .path-content {{
            padding: 2rem;
        }}

        .passage {{
            margin-bottom: 2rem;
        }}

        .passage-title {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #333;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #667eea;
        }}

        .passage-text {{
            color: #555;
            white-space: pre-wrap;
            line-height: 1.8;
        }}

        .toggle-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.875rem;
            margin-top: 1rem;
            transition: background 0.3s;
        }}

        .toggle-btn:hover {{
            background: #5568d3;
        }}

        .path-content.collapsed {{
            display: none;
        }}

        .footer {{
            text-align: center;
            padding: 2rem;
            color: #666;
            font-size: 0.875rem;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>All Story Paths - {story_data['name']}</h1>
        <div class="subtitle">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>

    <div class="stats">
        <h2>Statistics</h2>
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-label">Total Paths</div>
                <div class="stat-value">{len(all_paths)}</div>
            </div>
            <div class="stat-item" style="border-left-color: #007bff;">
                <div class="stat-label">New Paths</div>
                <div class="stat-value">{new_count}</div>
            </div>
            <div class="stat-item" style="border-left-color: #ffc107;">
                <div class="stat-label">Modified Paths</div>
                <div class="stat-value">{modified_count}</div>
            </div>
            <div class="stat-item" style="border-left-color: #28a745;">
                <div class="stat-label">Unchanged Paths</div>
                <div class="stat-value">{unchanged_count}</div>
            </div>
            <div class="stat-item" style="border-left-color: #6f42c1;">
                <div class="stat-label">Validated Paths</div>
                <div class="stat-value">{validated_count}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Shortest Path</div>
                <div class="stat-value">{min(path_lengths)} passages</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Longest Path</div>
                <div class="stat-value">{max(path_lengths)} passages</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Average Length</div>
                <div class="stat-value">{sum(path_lengths) / len(all_paths):.1f} passages</div>
            </div>
        </div>
    </div>

    <div class="filter-section">
        <div class="filter-buttons">
            <button class="filter-btn active" onclick="filterPaths('all')">All Paths</button>
            <button class="filter-btn" onclick="filterPaths('new')">New ({new_count})</button>
            <button class="filter-btn" onclick="filterPaths('modified')">Modified ({modified_count})</button>
            <button class="filter-btn" onclick="filterPaths('unchanged')">Unchanged ({unchanged_count})</button>
            <button class="filter-btn" onclick="toggleAllPaths()">Expand All</button>
            <button class="filter-btn" onclick="collapseAllPaths()">Collapse All</button>
        </div>
    </div>

    <div class="container">
'''

    # Generate each path (using sorted paths with metadata)
    for i, (path, path_hash, created_date, category) in enumerate(paths_with_metadata, 1):
        is_validated = validation_cache.get(path_hash, {}).get('validated', False)
        first_seen = validation_cache.get(path_hash, {}).get('first_seen', '')

        # Category badge
        category_badge_class = f'badge-{category}'
        category_text = category.capitalize()

        html += f'''
        <div class="path {category}" data-status="{category}">
            <div class="path-header">
                <div class="path-title">Path {i} of {len(all_paths)}</div>
                <div class="path-meta">
                    <div class="path-meta-item">
                        <span class="badge {category_badge_class}">{category_text}</span>
                    </div>'''

        if is_validated:
            html += '''
                    <div class="path-meta-item">
                        <span class="badge badge-validated">Validated</span>
                    </div>'''

        html += f'''
                    <div class="path-meta-item">
                        📏 Length: {len(path)} passages
                    </div>
                    <div class="path-meta-item">
                        🔑 ID: {path_hash}
                    </div>'''

        if created_date:
            # Format created date nicely
            try:
                from datetime import datetime as dt
                created_dt = dt.fromisoformat(created_date.replace('Z', '+00:00'))
                created_display = created_dt.strftime('%Y-%m-%d')
            except:
                created_display = created_date[:10] if len(created_date) >= 10 else created_date

            html += f'''
                    <div class="path-meta-item">
                        📅 Committed: {created_display}
                    </div>'''

        html += f'''
                    <div class="path-meta-item">
                        📄 <a href="allpaths-clean/path-{path_hash}.txt" style="color: #667eea; text-decoration: none;">Plain Text</a>
                    </div>
                </div>
                <div style="margin-top: 1rem;">
                    <div class="route">{' → '.join(path)}</div>
                </div>
                <button class="toggle-btn" onclick="togglePath(this)">Show Content</button>
            </div>
            <div class="path-content collapsed" id="path-{i}">
'''

        # Add each passage in the path
        for j, passage_name in enumerate(path):
            if passage_name not in passages:
                html += f'''
                <div class="passage">
                    <div class="passage-title">[{passage_name}]</div>
                    <div class="passage-text">[Passage not found]</div>
                </div>
'''
                continue

            passage = passages[passage_name]

            # Determine the next passage to filter links
            next_passage = path[j + 1] if j + 1 < len(path) else None
            formatted_text = format_passage_text(passage['text'], next_passage)

            html += f'''
                <div class="passage">
                    <div class="passage-title" style="font-size: 0.9rem; opacity: 0.7; font-style: italic;">[Passage: {passage_name}]</div>
                    <div class="passage-text">{formatted_text}</div>
                </div>
'''

        html += '''
            </div>
        </div>
'''

    html += '''
    </div>

    <div class="footer">
        Generated by AllPaths Story Format | For AI-based continuity checking
    </div>

    <script>
        function togglePath(button) {
            const content = button.closest('.path').querySelector('.path-content');
            const isCollapsed = content.classList.contains('collapsed');

            if (isCollapsed) {
                content.classList.remove('collapsed');
                button.textContent = 'Hide Content';
            } else {
                content.classList.add('collapsed');
                button.textContent = 'Show Content';
            }
        }

        function filterPaths(filter) {
            const paths = document.querySelectorAll('.path');
            const buttons = document.querySelectorAll('.filter-btn');

            // Update button states
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            // Filter paths
            paths.forEach(path => {
                if (filter === 'all') {
                    path.style.display = 'block';
                } else {
                    path.style.display = path.dataset.status === filter ? 'block' : 'none';
                }
            });
        }

        function toggleAllPaths() {
            const contents = document.querySelectorAll('.path-content');
            const buttons = document.querySelectorAll('.toggle-btn');

            contents.forEach(content => content.classList.remove('collapsed'));
            buttons.forEach(btn => btn.textContent = 'Hide Content');
        }

        function collapseAllPaths() {
            const contents = document.querySelectorAll('.path-content');
            const buttons = document.querySelectorAll('.toggle-btn');

            contents.forEach(content => content.classList.add('collapsed'));
            buttons.forEach(btn => btn.textContent = 'Show Content');
        }
    </script>
</body>
</html>
'''

    return html

def main():
    if len(sys.argv) < 2:
        print("Usage: generator.py <input.html> [output_dir]", file=sys.stderr)
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('.')

    # Read input HTML
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Parse story
    story_data, passages = parse_story_html(html_content)

    # Build graph
    graph = build_graph(passages)

    # Find start passage
    start_passage = None
    for name, passage in passages.items():
        if passage['pid'] == story_data['start']:
            start_passage = name
            break

    if not start_passage:
        start_passage = 'Start'

    # Generate all paths
    all_paths = generate_all_paths_dfs(graph, start_passage)

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

    # Categorize paths (New/Modified/Unchanged)
    path_categories = categorize_paths(all_paths, passages, validation_cache,
                                      passage_to_file, repo_root, base_ref)
    print(f"Categorized paths: {sum(1 for c in path_categories.values() if c == 'new')} new, "
          f"{sum(1 for c in path_categories.values() if c == 'modified')} modified, "
          f"{sum(1 for c in path_categories.values() if c == 'unchanged')} unchanged", file=sys.stderr)

    # Generate HTML output (uses original passage names for human readability)
    html_output = generate_html_output(story_data, passages, all_paths, validation_cache, path_categories)

    # Write HTML file
    html_file = output_dir / 'allpaths.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_output)

    print(f"Generated {html_file}", file=sys.stderr)

    # Generate individual text files for public deployment (clean prose, no metadata)
    text_dir = output_dir / 'allpaths-clean'
    text_dir.mkdir(exist_ok=True)

    for i, path in enumerate(all_paths, 1):
        path_hash = calculate_path_hash(path, passages)
        # Set include_metadata=False for clean prose output
        text_content = generate_path_text(path, passages, i, len(all_paths),
                                         include_metadata=False,
                                         passage_id_mapping=passage_id_mapping)

        # Use content-based hash only (no sequential index)
        text_file = text_dir / f'path-{path_hash}.txt'
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_content)

    print(f"Generated {len(all_paths)} text files in {text_dir} (clean prose)", file=sys.stderr)

    # Generate text files for AI continuity checking (with metadata and passage markers)
    continuity_dir = output_dir / 'allpaths-metadata'
    continuity_dir.mkdir(exist_ok=True)

    for i, path in enumerate(all_paths, 1):
        path_hash = calculate_path_hash(path, passages)
        # Set include_metadata=True for continuity checking with passage markers
        text_content = generate_path_text(path, passages, i, len(all_paths),
                                         include_metadata=True,
                                         passage_id_mapping=passage_id_mapping)

        # Use content-based hash only (no sequential index)
        text_file = continuity_dir / f'path-{path_hash}.txt'
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_content)

    print(f"Generated {len(all_paths)} text files in {continuity_dir} (with metadata)", file=sys.stderr)

    # Update validation cache with current paths (mark them as available for validation)
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

    save_validation_cache(cache_file, validation_cache)

    # Print summary
    print(f"\n=== AllPaths Generation Complete ===", file=sys.stderr)
    print(f"Story: {story_data['name']}", file=sys.stderr)
    print(f"Total paths: {len(all_paths)}", file=sys.stderr)
    print(f"Path lengths: {min(len(p) for p in all_paths)}-{max(len(p) for p in all_paths)} passages", file=sys.stderr)
    print(f"HTML output: {html_file}", file=sys.stderr)
    print(f"Text files (public): {text_dir}/", file=sys.stderr)
    print(f"Text files (continuity): {continuity_dir}/", file=sys.stderr)
    print(f"Passage mapping: {mapping_file}", file=sys.stderr)
    print(f"Validation cache: {cache_file}", file=sys.stderr)

if __name__ == '__main__':
    main()
