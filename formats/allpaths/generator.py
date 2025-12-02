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
from modules.categorizer import (
    calculate_route_hash,
    categorize_paths,
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
# Note: Text processing utilities moved to modules/categorizer.py (Step 3.4)
# - strip_links_from_text: Remove link syntax from prose
# - normalize_prose_for_comparison: Normalize whitespace for comparison
# - calculate_route_hash: Calculate hash for path route structure



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

# Note: generate_path_text moved to modules/output_generator.py (already duplicated there)

# =============================================================================
# VALIDATION CACHE
# =============================================================================

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
#
# Note: Git-based categorization functions moved to modules/categorizer.py (Step 3.4):
# - get_file_content_from_git
# - analyze_file_changes
# - parse_twee_content
# - build_paths_from_base_branch
# - categorize_paths (two-level categorization with PRIMARY and SECONDARY tests)

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

# =============================================================================
# OUTPUT GENERATION
# =============================================================================
# Note: Output generation functions moved to modules/output_generator.py
# - format_date_for_display
# - generate_html_output
# - save_validation_cache
# - generate_outputs

# =============================================================================
# CACHE MANAGEMENT
# =============================================================================

def update_validation_cache_with_paths(validation_cache: Dict, all_paths: List[List[str]],
                                      passages: Dict, path_categories: Dict[str, str],
                                      passage_to_file: Dict[str, Path], repo_root: Path) -> None:
    """Update validation cache with current paths and their metadata.

    Args:
        validation_cache: The cache dict to update (modified in place)
        all_paths: List of all paths
        passages: Dict of passage data
        path_categories: Dict mapping path hash to category
        passage_to_file: Mapping from passage names to file paths
        repo_root: Path to repository root
    """
    for path in all_paths:
        path_hash = calculate_path_hash(path, passages)
        commit_date = get_path_commit_date(path, passage_to_file, repo_root)
        creation_date = get_path_creation_date(path, passage_to_file, repo_root)
        category = path_categories.get(path_hash, 'new')

        if path_hash not in validation_cache:
            validation_cache[path_hash] = {
                'route': ' → '.join(path),
                'first_seen': datetime.now().isoformat(),
                'commit_date': commit_date,
                'created_date': creation_date,
                'category': category,
            }
        else:
            # Update commit date, created date, and category for existing entries
            validation_cache[path_hash]['commit_date'] = commit_date

            # Update created_date to reflect the earliest passage creation date
            if creation_date:
                validation_cache[path_hash]['created_date'] = creation_date

            # Always update category - it's computed fresh from git on each build
            validation_cache[path_hash]['category'] = category


def write_intermediate_story_graph(output_dir: Path, passages: Dict, graph: Dict,
                                  start_passage: str, story_data: Dict) -> None:
    """Write intermediate story_graph.json artifact for debugging.

    Args:
        output_dir: Output directory
        passages: Dict of passage data
        graph: Story graph (adjacency list)
        start_passage: Name of start passage
        story_data: Story metadata
    """
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


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> None:
    """Main entry point for AllPaths generator.

    Implements a 5-stage pipeline:
    - Stage 1: Load story_graph.json from core library
    - Stage 2: Generate all possible paths
    - Stage 3: Enrich paths with git metadata
    - Stage 4: Categorize paths (new/modified/unchanged)
    - Stage 5: Output generation (HTML, text files, cache)

    Usage:
        generator.py [output_dir] [--write-intermediate]

    Args:
        output_dir: Optional directory for output files (default: dist)
        --write-intermediate: Optional flag to write intermediate artifacts for debugging

    Outputs:
        - allpaths.html: Interactive HTML viewer with all paths
        - allpaths-clean/*.txt: Individual path files with clean prose
        - allpaths-metadata/*.txt: Individual path files with metadata
        - allpaths-passage-mapping.json: Mapping between passage names and IDs
        - allpaths-validation-status.json: Cache of path validation data

        When --write-intermediate is enabled:
        - dist/allpaths-intermediate/story_graph.json: Stage 1 output (story structure)
        - dist/allpaths-intermediate/paths.json: Stage 2 output (enumerated paths)
        - dist/allpaths-intermediate/paths_enriched.json: Stage 3 output (paths with git metadata)
        - dist/allpaths-intermediate/paths_categorized.json: Stage 4 output (categorized paths)
    """
    # =========================================================================
    # SETUP AND ARGUMENT PARSING
    # =========================================================================
    parser = argparse.ArgumentParser(
        description='AllPaths Story Format Generator - Generate all possible story paths for AI continuity checking'
    )
    parser.add_argument('output_dir', type=Path, nargs='?', default=Path('dist'),
                       help='Directory for output files (default: dist)')
    parser.add_argument('--write-intermediate', action='store_true', default=False,
                       help='Write intermediate artifacts to dist/allpaths-intermediate/ for debugging')

    args = parser.parse_args()

    output_dir = args.output_dir
    write_intermediate = args.write_intermediate

    # =========================================================================
    # STAGE 1: LOAD STORY GRAPH
    # =========================================================================
    print("\n" + "="*80, file=sys.stderr)
    print("STAGE 1: LOAD - Reading story_graph.json from core library", file=sys.stderr)
    print("="*80, file=sys.stderr)

    # Load story_graph.json from core library artifacts
    story_graph_path = output_dir.parent / 'lib' / 'artifacts' / 'story_graph.json'
    if not story_graph_path.exists():
        print(f"Error: Core artifact not found: {story_graph_path}", file=sys.stderr)
        print(f"Run 'npm run build:core' first to generate core artifacts", file=sys.stderr)
        sys.exit(1)

    with open(story_graph_path, 'r', encoding='utf-8') as f:
        story_graph = json.load(f)

    print(f"Loaded story_graph.json with {len(story_graph['passages'])} passages", file=sys.stderr)

    # Extract data from story_graph for compatibility with existing stages
    start_passage = story_graph['start_passage']
    metadata = story_graph['metadata']

    # Convert story_graph passages to old format for compatibility
    passages = {}
    for name, passage_data in story_graph['passages'].items():
        passages[name] = {
            'pid': '',  # PID not needed from story_graph
            'name': name,
            'tags': [],  # Tags not in story_graph
            'text': passage_data['content']
        }

    # Create story_data for compatibility
    story_data = {
        'name': metadata['story_title'],
        'ifid': metadata['ifid'],
        'start': '',  # Not needed, we have start_passage directly
        'format': metadata['format'],
        'format_version': metadata['format_version']
    }

    print(f"Story: {story_data['name']}", file=sys.stderr)
    print(f"Start passage: {start_passage}", file=sys.stderr)

    # Build graph representation (unchanged - still uses passages dict)
    graph = build_graph(passages)
    print(f"Built story graph with {len(graph)} nodes", file=sys.stderr)

    # Write intermediate artifact if requested
    if write_intermediate:
        write_intermediate_story_graph(output_dir, passages, graph, start_passage, story_data)

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

    # Write intermediate artifact if requested
    if write_intermediate:
        intermediate_dir = output_dir / 'allpaths-intermediate'
        intermediate_dir.mkdir(parents=True, exist_ok=True)

        # Build paths data structure matching paths.json schema
        paths_list = []
        for path in all_paths:
            path_id = calculate_path_hash(path, passages)
            content = {}
            for passage_name in path:
                if passage_name in passages:
                    content[passage_name] = passages[passage_name].get('text', '')
                else:
                    content[passage_name] = '[Passage not found]'

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

        paths_data = {
            'paths': paths_list,
            'statistics': {
                'total_paths': total_paths,
                'total_passages': total_passages,
                'avg_path_length': avg_path_length
            }
        }

        paths_file = intermediate_dir / 'paths.json'
        with open(paths_file, 'w', encoding='utf-8') as f:
            json.dump(paths_data, f, indent=2)

        print(f"[DEBUG] Wrote intermediate artifact: {paths_file}", file=sys.stderr)

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
    # Two explicit contexts - no automatic fallback:
    # 1. PR context: GITHUB_MERGE_BASE must be set (workflow calculates it)
    # 2. Local context: Use HEAD (no env vars set)
    merge_base = os.getenv('GITHUB_MERGE_BASE')
    github_base_ref = os.getenv('GITHUB_BASE_REF')

    if merge_base:
        # PR context with proper merge base - use it for accurate categorization
        base_ref = merge_base
        print(f"Using git base ref: {base_ref} (PR merge base)", file=sys.stderr)
    elif github_base_ref:
        # PR context but merge base not calculated - this is a workflow error
        print(f"[ERROR] GITHUB_BASE_REF is set ({github_base_ref}) but GITHUB_MERGE_BASE is not.", file=sys.stderr)
        print(f"[ERROR] The GitHub Actions workflow must calculate merge base for accurate categorization.", file=sys.stderr)
        print(f"[ERROR] Add: MERGE_BASE=$(git merge-base HEAD origin/$GITHUB_BASE_REF)", file=sys.stderr)
        sys.exit(1)
    else:
        # Local development context - use HEAD to detect uncommitted changes
        base_ref = 'HEAD'
        print(f"Using git base ref: {base_ref} (local development)", file=sys.stderr)

    # Verify that the base ref is accessible before proceeding
    if not verify_base_ref_accessible(repo_root, base_ref):
        print(f"[ERROR] Cannot access base ref '{base_ref}' - path categorization will be incorrect!", file=sys.stderr)
        print(f"[ERROR] All paths will be marked as 'new' instead of properly categorized.", file=sys.stderr)
        # Continue execution but warn user that results will be incorrect

    # Write intermediate artifact if requested
    if write_intermediate:
        intermediate_dir = output_dir / 'allpaths-intermediate'
        intermediate_dir.mkdir(parents=True, exist_ok=True)

        # Build paths_enriched data structure matching paths_enriched.json schema
        enriched_paths = []
        for path in all_paths:
            path_id = calculate_path_hash(path, passages)

            # Build content mapping
            content = {}
            for passage_name in path:
                if passage_name in passages:
                    content[passage_name] = passages[passage_name].get('text', '')
                else:
                    content[passage_name] = '[Passage not found]'

            # Collect git metadata
            files_in_path = []
            seen_files = set()
            passage_to_file_for_path = {}

            for passage_name in path:
                if passage_name in passage_to_file:
                    file_path = passage_to_file[passage_name]
                    # Convert to relative path for JSON output
                    relative_path = str(file_path.relative_to(repo_root))
                    passage_to_file_for_path[passage_name] = relative_path

                    # Track unique files
                    if relative_path not in seen_files:
                        files_in_path.append(relative_path)
                        seen_files.add(relative_path)

            # Get commit and creation dates for the path
            commit_date = get_path_commit_date(path, passage_to_file, repo_root)
            creation_date = get_path_creation_date(path, passage_to_file, repo_root)

            enriched_path = {
                'id': path_id,
                'route': path,
                'content': content,
                'git_metadata': {
                    'files': files_in_path,
                    'commit_date': commit_date,
                    'created_date': creation_date,
                    'passage_to_file': passage_to_file_for_path
                }
            }
            enriched_paths.append(enriched_path)

        # Build final structure
        total_paths = len(all_paths)
        total_passages = len(passages)
        avg_path_length = sum(len(p) for p in all_paths) / total_paths if total_paths > 0 else 0.0

        paths_enriched_data = {
            'paths': enriched_paths,
            'statistics': {
                'total_paths': total_paths,
                'total_passages': total_passages,
                'avg_path_length': avg_path_length
            }
        }

        paths_enriched_file = intermediate_dir / 'paths_enriched.json'
        with open(paths_enriched_file, 'w', encoding='utf-8') as f:
            json.dump(paths_enriched_data, f, indent=2)

        print(f"[DEBUG] Wrote intermediate artifact: {paths_enriched_file}", file=sys.stderr)

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
    update_validation_cache_with_paths(validation_cache, all_paths, passages,
                                      path_categories, passage_to_file, repo_root)
    print(f"Updated validation cache with {len(validation_cache)} total entries", file=sys.stderr)

    # Write intermediate artifact if requested
    if write_intermediate:
        intermediate_dir = output_dir / 'allpaths-intermediate'
        intermediate_dir.mkdir(parents=True, exist_ok=True)

        # Build paths_categorized data structure matching paths_categorized.json schema
        categorized_paths = []
        for path in all_paths:
            path_id = calculate_path_hash(path, passages)

            # Build content mapping
            content = {}
            for passage_name in path:
                if passage_name in passages:
                    content[passage_name] = passages[passage_name].get('text', '')
                else:
                    content[passage_name] = '[Passage not found]'

            # Collect git metadata (same as Stage 3)
            files_in_path = []
            seen_files = set()
            passage_to_file_for_path = {}

            for passage_name in path:
                if passage_name in passage_to_file:
                    file_path = passage_to_file[passage_name]
                    relative_path = str(file_path.relative_to(repo_root))
                    passage_to_file_for_path[passage_name] = relative_path

                    if relative_path not in seen_files:
                        files_in_path.append(relative_path)
                        seen_files.add(relative_path)

            commit_date = get_path_commit_date(path, passage_to_file, repo_root)
            creation_date = get_path_creation_date(path, passage_to_file, repo_root)

            # Get categorization data
            category = path_categories.get(path_id, 'new')
            first_seen = validation_cache.get(path_id, {}).get('first_seen', datetime.now().isoformat())

            categorized_path = {
                'id': path_id,
                'route': path,
                'content': content,
                'git_metadata': {
                    'files': files_in_path,
                    'commit_date': commit_date,
                    'created_date': creation_date,
                    'passage_to_file': passage_to_file_for_path
                },
                'category': category,
                'first_seen': first_seen
            }
            categorized_paths.append(categorized_path)

        # Build final structure with statistics
        total_paths = len(all_paths)
        total_passages = len(passages)
        avg_path_length = sum(len(p) for p in all_paths) / total_paths if total_paths > 0 else 0.0

        paths_categorized_data = {
            'paths': categorized_paths,
            'statistics': {
                'total_paths': total_paths,
                'total_passages': total_passages,
                'avg_path_length': avg_path_length,
                'new': new_count,
                'modified': modified_count,
                'unchanged': unchanged_count
            }
        }

        paths_categorized_file = intermediate_dir / 'paths_categorized.json'
        with open(paths_categorized_file, 'w', encoding='utf-8') as f:
            json.dump(paths_categorized_data, f, indent=2)

        print(f"[DEBUG] Wrote intermediate artifact: {paths_categorized_file}", file=sys.stderr)

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
