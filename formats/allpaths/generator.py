#!/usr/bin/env python3
"""
AllPaths Story Format Generator
Generates all possible story paths using depth-first search for AI-based continuity checking.
"""

import re
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
from typing import Dict, List, Tuple, Set

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
        selected_target: If provided, only show this link and mark others as [not selected]

    Returns:
        Formatted text with links converted to visible text
    """
    # Replace [[display->target]] with "display"
    # Replace [[target<-display]] with "display"
    # Replace [[target]] with "target"

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
                return f"[{display}] (not selected)"
        else:
            return display

    return re.sub(r'\[\[([^\]]+)\]\]', replace_link, text)

def calculate_path_hash(path: List[str]) -> str:
    """Calculate a stable hash for a path based on its route"""
    route_str = ' -> '.join(path)
    return hashlib.md5(route_str.encode()).hexdigest()[:8]

def generate_path_text(path: List[str], passages: Dict, path_num: int,
                      total_paths: int, include_metadata: bool = True) -> str:
    """Generate formatted text for a single path"""
    lines = []

    if include_metadata:
        lines.append("=" * 80)
        lines.append(f"PATH {path_num} of {total_paths}")
        lines.append("=" * 80)
        lines.append(f"Route: {' → '.join(path)}")
        lines.append(f"Length: {len(path)} passages")
        lines.append(f"Path ID: {calculate_path_hash(path)}")
        lines.append("=" * 80)
        lines.append("")

    for i, passage_name in enumerate(path):
        if passage_name not in passages:
            lines.append(f"\n[PASSAGE: {passage_name}]")
            lines.append("[Passage not found]")
            lines.append("")
            continue

        passage = passages[passage_name]

        # Add passage name as metadata (not user-visible in the game)
        lines.append(f"[PASSAGE: {passage_name}]")
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

def generate_html_output(story_data: Dict, passages: Dict, all_paths: List[List[str]],
                        validation_cache: Dict = None) -> str:
    """Generate HTML output with all paths"""
    if validation_cache is None:
        validation_cache = {}

    # Calculate statistics
    path_lengths = [len(p) for p in all_paths]
    total_passages = sum(path_lengths)

    # Count new vs validated paths
    new_paths = []
    validated_paths = []

    for path in all_paths:
        path_hash = calculate_path_hash(path)
        if path_hash in validation_cache:
            validated_paths.append(path)
        else:
            new_paths.append(path)

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

        .path.validated {{
            border-left: 5px solid #28a745;
        }}

        .path.new {{
            border-left: 5px solid #ffc107;
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

        .badge-validated {{
            background: #28a745;
            color: white;
        }}

        .badge-new {{
            background: #ffc107;
            color: #333;
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
            <div class="stat-item">
                <div class="stat-label">New Paths</div>
                <div class="stat-value">{len(new_paths)}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Validated Paths</div>
                <div class="stat-value">{len(validated_paths)}</div>
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
            <button class="filter-btn" onclick="filterPaths('new')">New Only ({len(new_paths)})</button>
            <button class="filter-btn" onclick="filterPaths('validated')">Validated Only ({len(validated_paths)})</button>
            <button class="filter-btn" onclick="toggleAllPaths()">Expand All</button>
            <button class="filter-btn" onclick="collapseAllPaths()">Collapse All</button>
        </div>
    </div>

    <div class="container">
'''

    # Generate each path
    for i, path in enumerate(all_paths, 1):
        path_hash = calculate_path_hash(path)
        is_validated = path_hash in validation_cache
        status_class = 'validated' if is_validated else 'new'
        badge_class = 'badge-validated' if is_validated else 'badge-new'
        badge_text = 'Validated' if is_validated else 'New'

        html += f'''
        <div class="path {status_class}" data-status="{status_class}">
            <div class="path-header">
                <div class="path-title">Path {i} of {len(all_paths)}</div>
                <div class="path-meta">
                    <div class="path-meta-item">
                        <span class="badge {badge_class}">{badge_text}</span>
                    </div>
                    <div class="path-meta-item">
                        📏 Length: {len(path)} passages
                    </div>
                    <div class="path-meta-item">
                        🔑 ID: {path_hash}
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

    # Load validation cache
    cache_file = output_dir / 'allpaths-validation-cache.json'
    validation_cache = load_validation_cache(cache_file)

    # Generate HTML output
    html_output = generate_html_output(story_data, passages, all_paths, validation_cache)

    # Write HTML file
    html_file = output_dir / 'allpaths.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_output)

    print(f"Generated {html_file}", file=sys.stderr)

    # Generate individual text files for AI processing
    text_dir = output_dir / 'allpaths-text'
    text_dir.mkdir(exist_ok=True)

    for i, path in enumerate(all_paths, 1):
        path_hash = calculate_path_hash(path)
        text_content = generate_path_text(path, passages, i, len(all_paths))

        text_file = text_dir / f'path-{i:03d}-{path_hash}.txt'
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_content)

    print(f"Generated {len(all_paths)} text files in {text_dir}", file=sys.stderr)

    # Update validation cache with current paths (mark them as available for validation)
    for path in all_paths:
        path_hash = calculate_path_hash(path)
        if path_hash not in validation_cache:
            validation_cache[path_hash] = {
                'route': ' → '.join(path),
                'first_seen': datetime.now().isoformat(),
                'validated': False,
            }

    save_validation_cache(cache_file, validation_cache)

    # Print summary
    print(f"\n=== AllPaths Generation Complete ===", file=sys.stderr)
    print(f"Story: {story_data['name']}", file=sys.stderr)
    print(f"Total paths: {len(all_paths)}", file=sys.stderr)
    print(f"Path lengths: {min(len(p) for p in all_paths)}-{max(len(p) for p in all_paths)} passages", file=sys.stderr)
    print(f"HTML output: {html_file}", file=sys.stderr)
    print(f"Text files: {text_dir}/", file=sys.stderr)
    print(f"Validation cache: {cache_file}", file=sys.stderr)

if __name__ == '__main__':
    main()
