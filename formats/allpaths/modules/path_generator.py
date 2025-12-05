#!/usr/bin/env python3
"""
Path Generator Module (Stage 2 of AllPaths Pipeline)

Generates all possible story paths using depth-first search.

Input: story_graph.json (from Stage 1: Parser)
Output: paths.json with enumerated paths, routes, and content

Functions:
- generate_paths(story_graph) -> Dict: Main entry point
- generate_all_paths_dfs(...): DFS traversal algorithm
- calculate_path_hash(...): Hash generation for path IDs
- format_passage_text(...): Text formatting utilities
"""

import hashlib
import re
from typing import Dict, List, Optional


# =============================================================================
# PATH GENERATION - DFS TRAVERSAL
# =============================================================================

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


# =============================================================================
# TEXT FORMATTING
# =============================================================================

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


def format_passage_text_raw(text: str) -> str:
    """
    Return passage text unmodified, preserving Twee link syntax.

    This function is used for the allpaths-raw output format, which needs
    to preserve [[link]] markers for validation tools like the Interactive
    Fiction Editor.

    Args:
        text: The passage text to format

    Returns:
        Unmodified text with [[link]] markers preserved
    """
    return text


# =============================================================================
# HASHING AND IDENTIFICATION
# =============================================================================

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


# =============================================================================
# MAIN ENTRY POINT - STAGE 2 INTERFACE
# =============================================================================

def generate_paths(story_graph: Dict, output_path: Optional[str] = None) -> Dict:
    """
    Generate all possible paths from story graph (Stage 2 of pipeline).

    Args:
        story_graph: Story graph dict from Stage 1 (parser) containing:
            - passages: Dict mapping passage name -> {text, pid, links}
            - start_passage: Name of starting passage
            - metadata: Story metadata
        output_path: Optional path to write paths.json (if None, only returns dict)

    Returns:
        Dict containing:
            - paths: List of path objects with id, route, content
            - statistics: Summary statistics (total_paths, total_passages, avg_path_length)

    Output conforms to schemas/paths.schema.json
    """
    import json
    from pathlib import Path

    # Extract data from story graph
    passages = story_graph.get('passages', {})
    start_passage = story_graph.get('start_passage', 'Start')

    # Build adjacency list for DFS
    graph = {}
    for name, passage_data in passages.items():
        links = passage_data.get('links', [])
        graph[name] = links

    # Handle empty story
    if not passages or start_passage not in graph:
        result = {
            'paths': [],
            'statistics': {
                'total_paths': 0,
                'total_passages': len(passages),
                'avg_path_length': 0.0
            }
        }

        # Write to file if requested
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)

        return result

    # Generate all paths using DFS
    all_paths = generate_all_paths_dfs(graph, start_passage)

    # Build paths list with id, route, and content
    paths_list = []
    for path in all_paths:
        # Calculate path hash (ID)
        path_id = calculate_path_hash(path, passages)

        # Build content mapping
        content = {}
        for passage_name in path:
            if passage_name in passages:
                content[passage_name] = passages[passage_name].get('text', '')
            else:
                content[passage_name] = '[Passage not found]'

        # Create path object
        path_obj = {
            'id': path_id,
            'route': path,
            'content': content
        }
        paths_list.append(path_obj)

    # Calculate statistics
    total_paths = len(all_paths)
    total_passages = len(passages)
    avg_path_length = sum(len(p) for p in all_paths) / total_paths if total_paths > 0 else 0.0

    statistics = {
        'total_paths': total_paths,
        'total_passages': total_passages,
        'avg_path_length': avg_path_length
    }

    # Build result
    result = {
        'paths': paths_list,
        'statistics': statistics
    }

    # Write to file if requested
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

    return result
