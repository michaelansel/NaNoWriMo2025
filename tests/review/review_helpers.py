"""Helpers for the review tests: fixture stories and model-answer builders."""

from __future__ import annotations

from pathlib import Path

from nanoif.review.units import ReviewStory, read_story_style
from nanoif.twee.files import passage_locations
from nanoif.twee.parse import parse_twee_dir

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
EVAL_SRC = FIXTURES / "eval-story" / "src"
REGRESSIONS = FIXTURES / "regressions"


def load_review_story(src: Path) -> ReviewStory:
    """Build the review view of a fixture story straight from its twee source."""
    locations = passage_locations(src)
    return ReviewStory.from_graph(
        parse_twee_dir(src),
        {name: location.tags for name, location in locations.items()},
        locations,
        read_story_style(src),
        src.parent,
    )


def path_finding(
    other_id: str,
    quotes: list[tuple[str, str]],
    finding_type: str = "number",
    severity: str = "major",
    confidence: str = "high",
    description: str = "The two passages disagree.",
) -> dict:
    """One continuity finding as the model would return it (source ``path``)."""
    return {
        "type": finding_type,
        "source": "path",
        "other": {"passage_id": other_id, "fact_id": None},
        "description": description,
        "severity": severity,
        "confidence": confidence,
        "quotes": [{"passage_id": pid, "text": text} for pid, text in quotes],
    }


def answer(*findings: dict) -> dict:
    """A schema-valid model answer."""
    return {"findings": list(findings), "notes": "Checked names, numbers and timeline."}
