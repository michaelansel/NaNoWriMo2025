"""Tests for ``nanoif.graph.ids``: passage ids and the PathIdLookup passage."""

import hashlib
import json

import pytest

from nanoif.graph.ids import (
    javascript_lookup,
    passage_id_mapping,
    path_id_lookup,
    render_path_id_lookup,
    write_path_id_lookup,
)
from nanoif.graph.paths import path_hash
from nanoif.twee.files import split_twee

STORY_GRAPH = {
    "start_passage": "Start",
    "passages": {
        "Start": {"content": "Beginning.\n\n[[Go left->Left]]\n[[Go right->Right]]", "links": ["Left", "Right"]},
        "Left": {"content": "You went left.\n\n[[End1]]", "links": ["End1"]},
        "Right": {"content": "You went right.\n\n[[End2]]", "links": ["End2"]},
        "End1": {"content": "Left ending (no links).", "links": []},
        "End2": {"content": "Right ending (no links).", "links": []},
    },
    "metadata": {"story_title": "Test Story", "ifid": "test-123", "format": "Harlowe", "format_version": "3.3.9"},
}


def test_passage_id_mapping_is_stable_md5_prefix_sorted_by_name():
    mapping = passage_id_mapping(["Start", "Day 5 AB", "End"])
    assert list(mapping) == ["Day 5 AB", "End", "Start"]
    assert mapping["Day 5 AB"] == hashlib.md5(b"Day 5 AB").hexdigest()[:12]
    assert mapping == passage_id_mapping(["End", "Start", "Day 5 AB"])
    assert all(len(v) == 12 and set(v) <= set("0123456789abcdef") for v in mapping.values())


@pytest.mark.intent("AC-output-formats-18")
def test_path_id_lookup_keys_are_arrow_joined_routes():
    content = {"Start": "Begin", "Left": "Go left", "End1": "Left ending"}
    lookup = path_id_lookup([["Start", "Left", "End1"]], content)
    assert lookup == {"Start→Left→End1": path_hash(["Start", "Left", "End1"], content)}


def test_path_id_lookup_empty():
    assert path_id_lookup([], {}) == {}


def test_javascript_lookup_is_a_single_statement_with_unescaped_unicode():
    js = javascript_lookup({"Start→It's here→End": "abc12345", "Start→Other": "bbb22222"})
    assert js.startswith("window.pathIdLookup = {") and js.endswith("};")
    assert "Start→It's here→End" in js and "abc12345" in js and "bbb22222" in js
    assert json.loads(js[len("window.pathIdLookup = ") : -1]) == {
        "Start→It's here→End": "abc12345",
        "Start→Other": "bbb22222",
    }
    assert javascript_lookup({}) == "window.pathIdLookup = {};"


@pytest.mark.intent("AC-output-formats-19")
def test_render_path_id_lookup_is_a_script_passage_with_every_route():
    twee, count = render_path_id_lookup(STORY_GRAPH)
    assert count == 2
    assert twee.startswith(":: PathIdLookup [script]\nwindow.pathIdLookup = {")
    assert "Start→Left→End1" in twee and "Start→Right→End2" in twee
    assert "window.getPathId = function(fullPath)" in twee
    assert "harlowe-history-data" in twee
    passages = split_twee(twee)
    assert [(p.name, p.tags) for p in passages] == [("PathIdLookup", ("script",))]


def test_write_path_id_lookup_writes_to_the_given_path(tmp_path):
    out = tmp_path / "src" / "PathIdLookup.twee"
    assert write_path_id_lookup(STORY_GRAPH, out) == 2
    assert out.read_text(encoding="utf-8") == render_path_id_lookup(STORY_GRAPH)[0]


def test_rendered_lookup_reads_the_footer_contract():
    """Ported from the retired scripts/test-path-id-lookup.js structural checks.

    The PathIdDisplay footer writes past passages joined by ``|||`` into
    ``#harlowe-history-data`` and the current passage into ``#harlowe-current-passage``;
    the lookup script must read both, split on ``|||``, and re-check on DOM changes.
    """
    twee, _ = render_path_id_lookup(STORY_GRAPH)
    for fragment in (
        "window.pathIdLookup = {",
        "window.getPathId = function(fullPath)",
        "function getCurrentPassage(",
        "function getFullPath(",
        "getElementById('harlowe-current-passage')",
        "getElementById('harlowe-history-data')",
        "split('|||')",
        "fullPath.join('→')",
        "new MutationObserver",
    ):
        assert fragment in twee, fragment
