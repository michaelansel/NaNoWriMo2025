#!/usr/bin/env python3
"""
Path ID Lookup Generator

Generates JavaScript lookup tables mapping passage history to path IDs.
This enables runtime display of unique path IDs at story endings.

Functions:
- generate_path_id_lookup(paths, passages) -> Dict: Create route→ID mapping
- generate_javascript_lookup(lookup) -> str: Generate JavaScript code
"""

import json
from typing import Dict, List
from path_generator import calculate_path_hash


def generate_path_id_lookup(paths: List[List[str]], passages: Dict) -> Dict[str, str]:
    """
    Generate lookup table mapping passage sequences to path IDs.

    Args:
        paths: List of paths, where each path is a list of passage names
        passages: Dict mapping passage name -> {text, pid, ...}

    Returns:
        Dict mapping "PassageA→PassageB→PassageC" -> "abc12345" (8-char hash)

    Example:
        paths = [['Start', 'Left', 'End1'], ['Start', 'Right', 'End2']]
        passages = {'Start': {...}, 'Left': {...}, ...}
        lookup = generate_path_id_lookup(paths, passages)
        # Returns:
        # {
        #   'Start→Left→End1': 'abc12345',
        #   'Start→Right→End2': 'def67890'
        # }
    """
    lookup = {}

    for path in paths:
        # Create key from passage sequence
        route_key = '→'.join(path)

        # Calculate hash using existing path_generator function
        path_id = calculate_path_hash(path, passages)

        lookup[route_key] = path_id

    return lookup


def generate_javascript_lookup(lookup: Dict[str, str]) -> str:
    """
    Generate JavaScript code that defines window.pathIdLookup.

    Args:
        lookup: Dict mapping passage route -> path ID

    Returns:
        JavaScript code string that can be embedded in <script> tag

    Example:
        lookup = {'Start→End': 'abc12345'}
        js = generate_javascript_lookup(lookup)
        # Returns:
        # window.pathIdLookup = {"Start→End": "abc12345"};
    """
    # Use json.dumps for proper JavaScript string escaping
    js_object = json.dumps(lookup, ensure_ascii=False, indent=2)

    # Generate JavaScript assignment
    js_code = f"window.pathIdLookup = {js_object};"

    return js_code
