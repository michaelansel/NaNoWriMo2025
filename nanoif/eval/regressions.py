"""Replay 2025's known Continuity false positives through the editor (AC-continuity-review-27).

Each fixture under ``tests/fixtures/regressions/<name>/`` is a tiny story (``src/``) and an
``expected.json`` naming the passage under review. The editor reviews that passage with the
real model; any finding it reports is a false positive, because the fixture was written
so that both statements are true. A failed call is an ``error``, never zero findings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nanoif.errors import BuildError
from nanoif.llm.client import Completer
from nanoif.llm.errors import LLMError
from nanoif.review import continuity
from nanoif.review.units import ReviewStory, continuity_units


def review_regressions(root: Path, client: Completer) -> dict[str, Any]:
    """Review every regression fixture under ``root``.

    Args:
        root: The ``regressions`` directory.
        client: The completer to evaluate.

    Returns:
        ``fixtures`` (``name``, ``status`` ``ok``/``error``, ``findings`` or ``None``,
        ``descriptions``, ``reason``), ``false_positives`` (findings across the fixtures
        that ran) and ``ok`` (every fixture ran).

    Raises:
        BuildError: A fixture is missing ``expected.json`` or it is not valid JSON.
    """
    fixtures: list[dict[str, Any]] = []
    for fixture in sorted(p for p in root.iterdir() if p.is_dir()):
        expected_path = fixture / "expected.json"
        try:
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BuildError(f"regression fixture {fixture.name}: {exc}") from exc
        story = ReviewStory.from_source(fixture / "src")
        unit = continuity_units(story, expected["passage_under_review"])[0]
        row: dict[str, Any] = {"name": fixture.name, "passage": unit.under_review.name}
        try:
            out = continuity.review_unit(client, story, unit)
        except LLMError as exc:
            row.update(status="error", findings=None, descriptions=[],
                       reason=f"{type(exc).__name__}: {exc}")
        else:
            row.update(status="ok", findings=len(out.findings),
                       descriptions=[f.description for f in out.findings], reason=None)
        fixtures.append(row)
    return {
        "fixtures": fixtures,
        "false_positives": sum(f["findings"] or 0 for f in fixtures),
        "ok": all(f["status"] == "ok" for f in fixtures),
    }
