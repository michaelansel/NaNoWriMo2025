#!/usr/bin/env python3
"""
AllPaths Output Generator Module (Stage 5)

Generates all output formats:
- HTML browser (using Jinja2 templates)
- Clean text files (prose only, with passage ID anonymization)
- Metadata text files (with path metadata and passage markers)
- Validation cache updates
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader


def format_date_for_display(date_str: str) -> str:
    """Format ISO date string to human-readable format (YYYY-MM-DD HH:MM UTC).

    Args:
        date_str: ISO format datetime string (e.g., "2025-01-15T10:30:00Z")

    Returns:
        Human-readable date string (e.g., "2025-01-15 10:30 UTC") or "Unknown"
    """
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
    """Generate HTML output with all paths using Jinja2 template.

    Args:
        story_data: Dict containing story metadata (name, ifid, start)
        passages: Dict mapping passage name -> passage data
        all_paths: List of all paths, where each path is a list of passage names
        validation_cache: Optional dict mapping path hash -> validation metadata
        path_categories: Optional dict mapping path hash -> category ('new', 'modified', 'unchanged')

    Returns:
        Rendered HTML string containing all paths with metadata and statistics
    """
    # Import calculate_path_hash from parent module
    import sys
    from pathlib import Path
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from generator import calculate_path_hash, format_passage_text

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

        # Format dates for display
        created_display = format_date_for_display(created_date)
        modified_display = format_date_for_display(commit_date)

        paths_with_metadata.append({
            'path': path,
            'path_hash': path_hash,
            'created_date': created_date,
            'commit_date': commit_date,
            'created_display': created_display,
            'modified_display': modified_display,
        })

    # Sort by creation date (newest first)
    # Use '0' as sentinel for missing dates - sorts before real ISO dates, ends up last with reverse=True
    paths_with_metadata.sort(key=lambda x: x['created_date'] if x['created_date'] else '0', reverse=True)

    # Set up Jinja2 environment
    template_dir = Path(__file__).parent.parent / 'templates'
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
        shortest_path=min(path_lengths) if path_lengths else 0,
        longest_path=max(path_lengths) if path_lengths else 0,
        average_length=f"{sum(path_lengths) / len(all_paths):.1f}" if all_paths else "0.0",
        paths_with_metadata=paths_with_metadata,
        passages=passages,
    )

    return html


def save_validation_cache(cache_file: Path, cache: Dict) -> None:
    """Save validated paths to cache.

    Args:
        cache_file: Path to the validation cache JSON file
        cache: Dict mapping path hash -> validation data
    """
    with open(cache_file, 'w') as f:
        json.dump(cache, indent=2, fp=f)


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
    # Import dependencies from parent module
    import sys
    from pathlib import Path
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from generator import calculate_path_hash, format_passage_text

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


def generate_outputs(
    story_data: Dict,
    passages: Dict,
    all_paths: List[List[str]],
    output_dir: Path,
    validation_cache: Optional[Dict] = None,
    path_categories: Optional[Dict[str, str]] = None,
    passage_id_mapping: Optional[Dict[str, str]] = None,
    cache_file: Optional[Path] = None
) -> Dict:
    """Generate all outputs from categorized paths data.

    This is the main entry point for Stage 5 (Output Generation).

    Args:
        story_data: Dict containing story metadata (name, ifid, start)
        passages: Dict mapping passage name -> passage data
        all_paths: List of all paths
        output_dir: Directory to write output files
        validation_cache: Optional dict mapping path hash -> validation metadata
        path_categories: Optional dict mapping path hash -> category
        passage_id_mapping: Optional mapping from passage names to anonymized IDs
        cache_file: Optional path to validation cache file

    Returns:
        Dict containing output file paths and statistics
    """
    # Import calculate_path_hash from parent module
    import sys
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from generator import calculate_path_hash

    if validation_cache is None:
        validation_cache = {}
    if path_categories is None:
        path_categories = {}

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate HTML output (uses original passage names for human readability)
    html_output = generate_html_output(story_data, passages, all_paths, validation_cache, path_categories)

    # Write HTML file
    html_file = output_dir / 'allpaths.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_output)

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

    # Save validation cache if provided
    if cache_file:
        save_validation_cache(cache_file, validation_cache)

    # Return result dictionary
    return {
        'html_file': str(html_file),
        'text_dir': str(text_dir),
        'metadata_dir': str(continuity_dir),
        'cache_file': str(cache_file) if cache_file else None,
        'total_paths': len(all_paths),
        'files_generated': {
            'html': 1,
            'clean_text': len(all_paths),
            'metadata_text': len(all_paths)
        }
    }
