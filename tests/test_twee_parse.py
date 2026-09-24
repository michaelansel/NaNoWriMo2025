"""Tests for the one story parser, ``nanoif.twee.parse``."""

import json

import pytest

from nanoif.errors import StoryParseError
from nanoif.schemas.artifacts import validate_artifact
from nanoif.twee.parse import build_graph, parse_story_html, parse_twee_dir, parse_twee_sources

SAMPLE_HTML = """
<!DOCTYPE html>
<html><body>
<tw-storydata name="Test Story" startnode="1" ifid="ABC-123" format="Harlowe" format-version="3.3.9">
  <tw-passagedata pid="1" name="Start" tags="">
    This is the start passage.
    [[Middle]]
    [[Skip to End-&gt;End]]
  </tw-passagedata>
  <tw-passagedata pid="2" name="Middle" tags="">You are in the middle. [[Continue to End->End]]</tw-passagedata>
  <tw-passagedata pid="3" name="End" tags="">This is the end.</tw-passagedata>
  <tw-passagedata pid="4" name="StoryTitle" tags="">Test Story</tw-passagedata>
  <tw-passagedata pid="5" name="StoryData" tags="">{"ifid": "ABC-123"}</tw-passagedata>
</tw-storydata>
</body></html>
"""


def test_parse_story_html_structure_and_metadata():
    result = parse_story_html(SAMPLE_HTML)
    assert set(result) == {"passages", "start_passage", "metadata"}
    assert result["start_passage"] == "Start"
    assert result["metadata"] == {
        "story_title": "Test Story",
        "ifid": "ABC-123",
        "format": "Harlowe",
        "format_version": "3.3.9",
    }


def test_parse_story_html_passages_and_links():
    result = parse_story_html(SAMPLE_HTML)
    assert set(result["passages"]) == {"Start", "Middle", "End"}
    assert result["passages"]["Start"]["links"] == ["Middle", "End"]
    assert result["passages"]["Middle"]["links"] == ["End"]
    assert result["passages"]["End"]["links"] == []
    assert "This is the start passage." in result["passages"]["Start"]["content"]
    assert "[[Middle]]" in result["passages"]["Start"]["content"]
    assert result["passages"]["Middle"]["content"] == "You are in the middle. [[Continue to End->End]]"


def test_parse_story_html_output_matches_schema():
    validate_artifact(parse_story_html(SAMPLE_HTML), "story_graph")


def test_parse_story_html_missing_format_attributes_default():
    html = """<tw-storydata name="Test" startnode="1">
        <tw-passagedata pid="1" name="Start">Story starts here.</tw-passagedata>
    </tw-storydata>"""
    result = parse_story_html(html)
    assert result["metadata"]["format"] == "Unknown"
    assert result["metadata"]["format_version"] == "Unknown"
    assert result["metadata"]["ifid"] == ""


def test_parse_story_html_link_formats():
    html = """<tw-storydata name="Test" startnode="1">
        <tw-passagedata pid="1" name="Start">
            Simple: [[Target1]]
            Display: [[Click here->Target2]]
            Reverse: [[Target3<-Different text]]
        </tw-passagedata>
    </tw-storydata>"""
    assert parse_story_html(html)["passages"]["Start"]["links"] == ["Target1", "Target2", "Target3"]


def test_parse_story_html_empty_passage():
    html = """<tw-storydata name="Empty" startnode="1">
        <tw-passagedata pid="1" name="Start"></tw-passagedata>
    </tw-storydata>"""
    result = parse_story_html(html)
    assert result["passages"]["Start"] == {"content": "", "links": []}


def test_parse_story_html_start_passage_by_pid_not_name():
    html = """<tw-storydata name="Test" startnode="5">
        <tw-passagedata pid="1" name="Start">Not the start!</tw-passagedata>
        <tw-passagedata pid="5" name="Beginning">This is the start.</tw-passagedata>
    </tw-storydata>"""
    assert parse_story_html(html)["start_passage"] == "Beginning"


def test_parse_story_html_no_passages_is_an_error():
    with pytest.raises(StoryParseError, match="no passages"):
        parse_story_html('<tw-storydata name="Empty" startnode="1"></tw-storydata>')


def test_parse_story_html_unknown_startnode_is_an_error():
    html = """<tw-storydata name="Test" startnode="9">
        <tw-passagedata pid="1" name="Start">x</tw-passagedata>
    </tw-storydata>"""
    with pytest.raises(StoryParseError, match="startnode"):
        parse_story_html(html)


def test_parse_story_html_not_a_story_is_an_error():
    with pytest.raises(StoryParseError, match="tw-storydata"):
        parse_story_html("<html><body>hello</body></html>")


STORY_DATA = json.dumps({"ifid": "ABC-123", "format": "Harlowe", "format-version": "3.3.9", "start": "Day 1 AB"})

TWEE_SOURCES = {
    "src/StoryData.twee": f":: StoryData\n{STORY_DATA}\n",
    "src/StoryTitle.twee": ":: StoryTitle\nTest Story\n",
    "src/AB-20251101.twee": ":: Day 1 AB\nMorning. [[Go->Day 2 AB]] or [[Stay]]\n\n:: Stay\nYou stay.\n",
    "src/AB-20251102.twee": ":: Day 2 AB\nNext day.\n",
}


def test_parse_twee_sources_matches_html_parser_shape():
    result = parse_twee_sources(TWEE_SOURCES)
    assert result["start_passage"] == "Day 1 AB"
    assert result["metadata"] == {
        "story_title": "Test Story",
        "ifid": "ABC-123",
        "format": "Harlowe",
        "format_version": "3.3.9",
    }
    assert set(result["passages"]) == {"Day 1 AB", "Stay", "Day 2 AB"}
    assert result["passages"]["Day 1 AB"] == {
        "content": "Morning. [[Go->Day 2 AB]] or [[Stay]]",
        "links": ["Day 2 AB", "Stay"],
    }
    validate_artifact(result, "story_graph")


def test_parse_twee_sources_start_comes_from_story_data_not_a_hardcoded_name():
    sources = dict(TWEE_SOURCES)
    sources["src/Start.twee"] = ":: Start\nNot the start.\n"
    assert parse_twee_sources(sources)["start_passage"] == "Day 1 AB"


def test_parse_twee_sources_defaults_to_start_when_story_data_has_no_start():
    sources = {
        "StoryData.twee": ':: StoryData\n{"ifid": "X"}\n',
        "Start.twee": ":: Start\nHi\n",
    }
    assert parse_twee_sources(sources)["start_passage"] == "Start"


def test_parse_twee_sources_skips_script_and_stylesheet_passages_like_tweego():
    sources = dict(TWEE_SOURCES)
    sources["src/StoryStyles.twee"] = (
        ":: StoryStylesheet [stylesheet]\nbody { color: red }\n\n:: Footer [footer]\nfoot\n"
    )
    sources["src/PathIdLookup.twee"] = ":: PathIdLookup [script]\nwindow.x = 1;\n"
    passages = parse_twee_sources(sources)["passages"]
    assert "StoryStylesheet" not in passages and "PathIdLookup" not in passages
    assert passages["Footer"] == {"content": "foot", "links": []}


def test_parse_twee_sources_missing_start_is_an_error():
    with pytest.raises(StoryParseError, match="start passage"):
        parse_twee_sources({"a.twee": ":: Elsewhere\nHi\n"})


def test_parse_twee_sources_invalid_story_data_is_an_error():
    with pytest.raises(StoryParseError, match="StoryData"):
        parse_twee_sources({"a.twee": ":: StoryData\n{not json\n\n:: Start\nHi\n"})


def test_parse_twee_sources_no_passages_is_an_error():
    with pytest.raises(StoryParseError, match="no passages"):
        parse_twee_sources({"a.twee": "just prose, no header\n"})


def test_parse_twee_dir_reads_files(tmp_path):
    for name, text in TWEE_SOURCES.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert parse_twee_dir(tmp_path / "src") == parse_twee_sources(TWEE_SOURCES)


def test_build_graph_is_adjacency_in_link_order():
    graph = build_graph(parse_twee_sources(TWEE_SOURCES))
    assert graph == {"Day 1 AB": ["Day 2 AB", "Stay"], "Stay": [], "Day 2 AB": []}
