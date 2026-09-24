"""Tests for ``nanoif build core``."""

import json

import pytest

from nanoif.build.core import build_core
from nanoif.cli import main
from nanoif.errors import BuildError

HTML = """<tw-storydata name="Test Story" startnode="1" ifid="ABC-123" format="Paperthin" format-version="1.0.0">
<tw-passagedata pid="1" name="Start">Beginning. [[Go left->Left]] [[Go right->Right]]</tw-passagedata>
<tw-passagedata pid="2" name="Left">Left. [[End1]]</tw-passagedata>
<tw-passagedata pid="3" name="Right">Right. [[End2]]</tw-passagedata>
<tw-passagedata pid="4" name="End1">Left ending.</tw-passagedata>
<tw-passagedata pid="5" name="End2">Right ending.</tw-passagedata>
<tw-passagedata pid="6" name="StoryData">{"ifid": "ABC-123"}</tw-passagedata>
</tw-storydata>"""


@pytest.fixture
def project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "story-paperthin.html").write_text(HTML, encoding="utf-8")
    return tmp_path


def test_build_core_writes_artifacts_and_lookup(project):
    result = build_core(
        html_path=project / "dist" / "story-paperthin.html",
        src_dir=project / "src",
        out_dir=project / "lib" / "artifacts",
        lookup_path=project / "src" / "PathIdLookup.twee",
    )
    assert result.passage_count == 5 and result.start_passage == "Start" and result.path_count == 2
    graph = json.loads((project / "lib" / "artifacts" / "story_graph.json").read_text())
    assert graph["passages"]["Start"]["links"] == ["Left", "Right"]
    assert "StoryData" not in graph["passages"]
    passages = json.loads((project / "lib" / "artifacts" / "passages_deduplicated.json").read_text())
    assert [p["name"] for p in passages["passages"]] == ["End1", "End2", "Left", "Right", "Start"]
    lookup = (project / "src" / "PathIdLookup.twee").read_text()
    assert lookup.startswith(":: PathIdLookup [script]\n")
    assert "Start→Left→End1" in lookup and "Start→Right→End2" in lookup


def test_build_core_missing_html_is_an_error(project):
    with pytest.raises(BuildError, match="compiled story not found"):
        build_core(project / "dist" / "missing.html", project / "src", project / "out", project / "x.twee")


def test_build_core_missing_src_is_an_error(project):
    with pytest.raises(BuildError, match="source directory"):
        build_core(project / "dist" / "story-paperthin.html", project / "nope", project / "out", project / "x.twee")


def test_cli_build_core_reports_and_defaults_lookup_path(project, capsys):
    argv = [
        "build",
        "core",
        "--html",
        str(project / "dist" / "story-paperthin.html"),
        "--src",
        str(project / "src"),
        "--out",
        str(project / "lib" / "artifacts"),
    ]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "Parsed 5 passages; start passage: Start" in out
    assert (project / "src" / "PathIdLookup.twee").exists()


def test_cli_build_core_error_is_reported_not_raised(project, capsys):
    argv = ["build", "core", "--html", str(project / "nope.html"), "--src", str(project / "src"), "--out", str(project)]
    assert main(argv) == 1
    assert "error: compiled story not found" in capsys.readouterr().err


def test_cli_build_without_target_prints_help(capsys):
    assert main(["build"]) == 2
    assert "usage: nanoif build" in capsys.readouterr().out
