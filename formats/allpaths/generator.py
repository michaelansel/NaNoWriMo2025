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
from jinja2 import Environment, FileSystemLoader

from lib.git_service import GitService

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

            # Find all passage declarations (:: PassageName or ::PassageName)
            # Allow optional space after :: to handle both formats
            passages_in_file = re.findall(r'^::\s*(.+?)(?:\s*\[.*?\])?\s*$', content, re.MULTILINE)

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
    """
    git_service = GitService(repo_root)
    return git_service.get_file_commit_date(file_path)

def get_file_creation_date(file_path: Path, repo_root: Path) -> Optional[str]:
    """
    Get the earliest commit date for a file (when it was first added).

    Args:
        file_path: Path to the file
        repo_root: Path to git repository root

    Returns:
        ISO format datetime string of earliest commit, or None if unavailable
    """
    git_service = GitService(repo_root)
    return git_service.get_file_creation_date(file_path)

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

    print(f"\n[INFO] ===== Categorization Complete =====", file=sys.stderr)
    print(f"[INFO] Total files checked: {total_files_checked}", file=sys.stderr)
    print(f"[INFO] Git lookups: {git_lookups_succeeded} succeeded, {git_lookups_failed} failed", file=sys.stderr)
    print(f"[INFO] Category breakdown:", file=sys.stderr)
    print(f"[INFO]   - NEW: {new_count} paths", file=sys.stderr)
    print(f"[INFO]   - MODIFIED: {modified_count} paths", file=sys.stderr)
    print(f"[INFO]   - UNCHANGED: {unchanged_count} paths", file=sys.stderr)

    return categories

def format_date_for_display(date_str: str) -> str:
    """Format ISO date string to human-readable format (YYYY-MM-DD HH:MM UTC)"""
    if not date_str:
        return "Unknown"
    try:
        from datetime import datetime as dt
        # Parse date with timezone info
        date_dt = dt.fromisoformat(date_str.replace('Z', '+00:00'))
        # Convert to UTC if it has timezone info
        if date_dt.tzinfo is not None:
            # Convert to UTC
            import datetime
            utc_dt = date_dt.astimezone(datetime.timezone.utc)
            return utc_dt.strftime('%Y-%m-%d %H:%M UTC')
        else:
            # Assume it's already UTC if no timezone
            return date_dt.strftime('%Y-%m-%d %H:%M UTC')
    except:
        # Fallback to just showing the date part
        return date_str[:10] if len(date_str) >= 10 else date_str

def generate_html_output(story_data: Dict, passages: Dict, all_paths: List[List[str]],
                        validation_cache: Dict = None, path_categories: Dict[str, str] = None) -> str:
    """Generate HTML output with all paths using Jinja2 template"""
    if validation_cache is None:
        validation_cache = {}
    if path_categories is None:
        path_categories = {}

    # Calculate statistics
    path_lengths = [len(p) for p in all_paths]

    # Prepare paths with metadata (no sorting by category - ADR-007 single interface)
    paths_with_metadata = []
    for path in all_paths:
        path_hash = calculate_path_hash(path, passages)
        created_date = validation_cache.get(path_hash, {}).get('created_date', '')
        commit_date = validation_cache.get(path_hash, {}).get('commit_date', '')
        is_validated = validation_cache.get(path_hash, {}).get('validated', False)

        # Format dates for display
        created_display = format_date_for_display(created_date)
        modified_display = format_date_for_display(commit_date)

        paths_with_metadata.append({
            'path': path,
            'path_hash': path_hash,
            'created_date': created_date,
            'commit_date': commit_date,
            'is_validated': is_validated,
            'created_display': created_display,
            'modified_display': modified_display,
        })

    # Sort by creation date (newest first)
    # Use '0' as sentinel for missing dates - sorts before real ISO dates, ends up last with reverse=True
    paths_with_metadata.sort(key=lambda x: x['created_date'] if x['created_date'] else '0', reverse=True)

    # Count validation status
    validated_count = sum(1 for p in paths_with_metadata if p['is_validated'])
    new_count = len(paths_with_metadata) - validated_count

    # Set up Jinja2 environment
    template_dir = Path(__file__).parent / 'templates'
    env = Environment(loader=FileSystemLoader(str(template_dir)))

    # Register format_passage_text as a global function for the template
    env.globals['format_passage_text'] = format_passage_text

    # Load template
    template = env.get_template('allpaths.html.jinja2')

    # Render template with context
    html = template.render(
        story_name=story_data['name'],
        generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        total_paths=len(all_paths),
        validated_count=validated_count,
        new_count=new_count,
        shortest_path=min(path_lengths),
        longest_path=max(path_lengths),
        average_length=f"{sum(path_lengths) / len(all_paths):.1f}",
        paths_with_metadata=paths_with_metadata,
        passages=passages,
    )

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

    # Verify that the base ref is accessible before proceeding
    if not verify_base_ref_accessible(repo_root, base_ref):
        print(f"[ERROR] Cannot access base ref '{base_ref}' - path categorization will be incorrect!", file=sys.stderr)
        print(f"[ERROR] All paths will be marked as 'new' instead of properly categorized.", file=sys.stderr)
        # Continue execution but warn user that results will be incorrect

    # Categorize paths (New/Modified/Unchanged)
    path_categories = categorize_paths(all_paths, passages, validation_cache,
                                      passage_to_file, repo_root, base_ref)
    print(f"Categorized paths: {sum(1 for c in path_categories.values() if c == 'new')} new, "
          f"{sum(1 for c in path_categories.values() if c == 'modified')} modified, "
          f"{sum(1 for c in path_categories.values() if c == 'unchanged')} unchanged", file=sys.stderr)

    # Update validation cache with current paths BEFORE generating HTML
    # This ensures HTML has access to fresh dates
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

    # Save validation cache (already updated with dates before HTML generation)
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
