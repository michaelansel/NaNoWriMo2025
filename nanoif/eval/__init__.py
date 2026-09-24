"""Prompt evaluation: score extractor and editor output against the eval story's truth."""

from pathlib import Path

from nanoif.eval.report import diff_against_baseline, render_markdown, to_json
from nanoif.eval.score import run_scoring

TRUTH_SCHEMA = Path(__file__).resolve().parent / "truth.schema.json"
"""Schema for ``tests/fixtures/eval-story/truth.json``, the eval story's answer key."""

__all__ = ["TRUTH_SCHEMA", "diff_against_baseline", "render_markdown", "run_scoring", "to_json"]
