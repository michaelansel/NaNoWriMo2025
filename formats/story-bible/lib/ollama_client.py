#!/usr/bin/env python3
"""
Ollama HTTP API client wrapper.

Provides a clean interface for calling Ollama for AI-based fact extraction.
"""

import requests
import time
import sys
from typing import Optional


# Ollama configuration (matches check-story-continuity.py)
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 60  # 60 second timeout per passage


def call_ollama(prompt: str, model: str = OLLAMA_MODEL, timeout: int = OLLAMA_TIMEOUT) -> Optional[str]:
    """
    Call Ollama HTTP API with a prompt and return the response.

    Args:
        prompt: The prompt to send to Ollama
        model: The Ollama model to use (default: gpt-oss:20b-fullcontext)
        timeout: Timeout in seconds (default: 60)

    Returns:
        Response text from Ollama, or None if request failed

    Raises:
        requests.Timeout: If request times out
        requests.RequestException: If request fails
    """
    try:
        print(f"  Calling Ollama API (model: {model})...", file=sys.stderr)
        start_time = time.time()

        response = requests.post(
            OLLAMA_API_URL,
            json={
                'model': model,
                'prompt': prompt,
                'stream': False
            },
            timeout=timeout
        )

        elapsed = time.time() - start_time
        print(f"  Ollama responded in {elapsed:.1f}s", file=sys.stderr)

        if response.status_code != 200:
            print(f"  Error calling Ollama: HTTP {response.status_code}", file=sys.stderr)
            print(f"  Response: {response.text[:200]}", file=sys.stderr)
            return None

        result = response.json()
        return result.get('response', '')

    except requests.Timeout:
        print(f"  Ollama request timed out after {timeout}s", file=sys.stderr)
        raise
    except requests.RequestException as e:
        print(f"  Error calling Ollama: {e}", file=sys.stderr)
        raise


def check_ollama_available() -> bool:
    """
    Check if Ollama service is available.

    Returns:
        True if Ollama is accessible, False otherwise
    """
    try:
        # Try to connect to Ollama API
        response = requests.get(
            "http://localhost:11434/api/tags",
            timeout=5
        )
        return response.status_code == 200
    except:
        return False
