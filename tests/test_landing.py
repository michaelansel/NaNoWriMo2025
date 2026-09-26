"""The landing page takes its title from ``StoryTitle`` (via ``story_graph.json``)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nanoif.errors import BuildError
from nanoif.formats.landing import TITLE_MARKER, build_landing

REPO = Path(__file__).resolve().parents[1]


def graph(tmp_path: Path, title: str) -> Path:
    path = tmp_path / "story_graph.json"
    path.write_text(json.dumps({"metadata": {"story_title": title}}), encoding="utf-8")
    return path


@pytest.mark.intent("AC-output-formats-3")
def test_landing_shows_the_story_title_escaped(tmp_path):
    template = tmp_path / "index.html"
    template.write_text(f"<title>{TITLE_MARKER}</title><h1>{TITLE_MARKER}</h1>", encoding="utf-8")
    out = build_landing(template, graph(tmp_path, "The Ferry & the <Weir>"), tmp_path / "dist")
    html = out.read_text(encoding="utf-8")
    assert html == "<title>The Ferry &amp; the &lt;Weir&gt;</title><h1>The Ferry &amp; the &lt;Weir&gt;</h1>"
    assert out == tmp_path / "dist" / "index.html"


@pytest.mark.intent("AC-output-formats-3")
def test_repository_landing_page_has_no_hardcoded_title():
    html = (REPO / "landing" / "index.html").read_text(encoding="utf-8")
    assert html.count(TITLE_MARKER) >= 2
    assert "NaNoWriMo 20" not in html


def test_template_without_the_marker_is_a_build_error(tmp_path):
    template = tmp_path / "index.html"
    template.write_text("<h1>Fixed title</h1>", encoding="utf-8")
    with pytest.raises(BuildError, match="STORY_TITLE"):
        build_landing(template, graph(tmp_path, "T"), tmp_path / "dist")
