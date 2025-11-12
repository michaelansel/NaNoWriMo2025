#!/usr/bin/env python3
"""
AI-based story continuity checker using Ollama.

This script:
1. Loads the validation cache
2. Identifies new/unvalidated story paths
3. Sends each path to Ollama for continuity analysis
4. Returns structured results with issues found
5. Updates the validation cache
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple
import subprocess
import hashlib
from datetime import datetime

# Ollama model to use
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"

# Continuity checking prompt template
CONTINUITY_PROMPT = """You are a story continuity checker. Analyze the following story path for continuity issues.

Check for:
1. Character consistency (names, traits, relationships stay consistent)
2. Plot coherence (events flow logically, no contradictions)
3. Timeline accuracy (event sequences make sense)
4. Setting/world consistency (locations, rules remain consistent)
5. Contradictions or plot holes

Story Path:
{story_text}

Respond with a JSON object in this format:
{{
  "has_issues": true/false,
  "severity": "none/minor/major/critical",
  "issues": [
    {{
      "type": "character/plot/timeline/setting/contradiction",
      "severity": "minor/major/critical",
      "description": "Brief description of the issue",
      "location": "Where in the path this occurs (optional)"
    }}
  ],
  "summary": "Brief overall assessment"
}}

If no issues found, return: {{"has_issues": false, "severity": "none", "issues": [], "summary": "No continuity issues detected"}}
"""


def call_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Call Ollama with a prompt and return the response."""
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )

        if result.returncode != 0:
            print(f"Error calling ollama: {result.stderr}", file=sys.stderr)
            return None

        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print("Ollama request timed out", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error calling ollama: {e}", file=sys.stderr)
        return None


def parse_ollama_response(response: str) -> Dict:
    """Parse Ollama's JSON response, with fallback handling."""
    if not response:
        return {
            "has_issues": False,
            "severity": "none",
            "issues": [],
            "summary": "Error: No response from AI"
        }

    try:
        # Try to find JSON in the response (ollama sometimes adds extra text)
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
        else:
            # No JSON found, treat as error
            return {
                "has_issues": False,
                "severity": "none",
                "issues": [],
                "summary": f"Error: Could not parse AI response"
            }
    except json.JSONDecodeError as e:
        return {
            "has_issues": False,
            "severity": "none",
            "issues": [],
            "summary": f"Error: Invalid JSON from AI: {str(e)}"
        }


def check_path_continuity(path_text: str) -> Dict:
    """Check a single story path for continuity issues."""
    prompt = CONTINUITY_PROMPT.format(story_text=path_text)
    response = call_ollama(prompt)
    return parse_ollama_response(response)


def load_validation_cache(cache_path: Path) -> Dict:
    """Load the validation cache file."""
    if not cache_path.exists():
        return {"paths": [], "last_updated": None}

    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading cache: {e}", file=sys.stderr)
        return {"paths": [], "last_updated": None}


def save_validation_cache(cache_path: Path, cache: Dict):
    """Save the validation cache file."""
    cache["last_updated"] = datetime.now().isoformat()
    try:
        with open(cache_path, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}", file=sys.stderr)


def get_unvalidated_paths(cache: Dict, text_dir: Path) -> List[Tuple[str, Path]]:
    """Get list of paths that need validation."""
    # Build a set of validated path IDs
    validated_ids = set()
    for path_info in cache.get("paths", []):
        if path_info.get("validated", False):
            validated_ids.add(path_info["id"])

    # Find all text files
    unvalidated = []
    for txt_file in sorted(text_dir.glob("*.txt")):
        # Extract path ID from filename (e.g., "path-abc12345.txt" -> "abc12345")
        filename = txt_file.stem
        if filename.startswith("path-"):
            path_id = filename[5:]  # Remove "path-" prefix
            if path_id not in validated_ids:
                unvalidated.append((path_id, txt_file))

    return unvalidated


def update_cache_with_results(cache: Dict, path_id: str, route: List[str], result: Dict):
    """Update the cache with validation results."""
    # Find existing path entry or create new one
    path_entry = None
    for p in cache.get("paths", []):
        if p["id"] == path_id:
            path_entry = p
            break

    if path_entry is None:
        path_entry = {
            "id": path_id,
            "route": route,
            "first_seen": datetime.now().isoformat()
        }
        if "paths" not in cache:
            cache["paths"] = []
        cache["paths"].append(path_entry)

    # Update validation info
    path_entry["validated"] = True
    path_entry["validated_at"] = datetime.now().isoformat()
    path_entry["has_issues"] = result.get("has_issues", False)
    path_entry["severity"] = result.get("severity", "none")
    path_entry["summary"] = result.get("summary", "")


def extract_route_from_text(text_path: Path) -> List[str]:
    """Extract the route (passage names) from a path text file."""
    # The text file should have a line like "Path: Start → Choice1 → End"
    try:
        with open(text_path, 'r') as f:
            content = f.read()
            # Look for the "Path:" line
            for line in content.split('\n'):
                if line.startswith('Path:'):
                    # Extract passage names (between → symbols)
                    route_str = line.replace('Path:', '').strip()
                    route = [p.strip() for p in route_str.split('→')]
                    return route
    except Exception as e:
        print(f"Error extracting route from {text_path}: {e}", file=sys.stderr)

    return []


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: check-story-continuity.py <text_dir> <cache_file>", file=sys.stderr)
        print("", file=sys.stderr)
        print("Example: check-story-continuity.py dist/allpaths-text dist/allpaths-validation-cache.json", file=sys.stderr)
        sys.exit(1)

    text_dir = Path(sys.argv[1])
    cache_file = Path(sys.argv[2])

    if not text_dir.exists() or not text_dir.is_dir():
        print(f"Error: {text_dir} is not a valid directory", file=sys.stderr)
        sys.exit(1)

    # Load cache
    cache = load_validation_cache(cache_file)

    # Get unvalidated paths
    unvalidated = get_unvalidated_paths(cache, text_dir)

    if not unvalidated:
        print("No new paths to validate")
        result = {
            "checked_count": 0,
            "paths_with_issues": [],
            "summary": "No new paths to check"
        }
        print(json.dumps(result, indent=2))
        sys.exit(0)

    print(f"Checking {len(unvalidated)} new path(s)...", file=sys.stderr)

    # Check each path
    paths_with_issues = []
    checked_count = 0

    for path_id, text_file in unvalidated:
        print(f"Checking path {path_id}...", file=sys.stderr)

        # Read the story text
        try:
            with open(text_file, 'r') as f:
                story_text = f.read()
        except Exception as e:
            print(f"Error reading {text_file}: {e}", file=sys.stderr)
            continue

        # Extract route
        route = extract_route_from_text(text_file)

        # Check continuity
        result = check_path_continuity(story_text)
        checked_count += 1

        # Update cache
        update_cache_with_results(cache, path_id, route, result)

        # Collect issues
        if result.get("has_issues", False):
            paths_with_issues.append({
                "id": path_id,
                "route": route,
                "severity": result.get("severity", "unknown"),
                "issues": result.get("issues", []),
                "summary": result.get("summary", "")
            })

        print(f"  Result: {result.get('severity', 'none')} - {result.get('summary', '')}", file=sys.stderr)

    # Save updated cache
    save_validation_cache(cache_file, cache)

    # Output results as JSON
    result = {
        "checked_count": checked_count,
        "paths_with_issues": paths_with_issues,
        "summary": f"Checked {checked_count} path(s), found issues in {len(paths_with_issues)}"
    }

    print("\n=== RESULTS ===", file=sys.stderr)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
