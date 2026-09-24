"""Tests for ``nanoif.graph.paths``: enumeration, broken links, cycles, hashes."""

import hashlib

import pytest

from nanoif.errors import GraphError
from nanoif.graph.paths import PathEnumeration, enumerate_paths, path_hash, route_hash


def test_enumerate_linear_story_has_one_path():
    result = enumerate_paths({"Start": ["Middle"], "Middle": ["End"], "End": []}, "Start")
    assert result == PathEnumeration(paths=[["Start", "Middle", "End"]])


def test_enumerate_branching_story_follows_link_order():
    graph = {"Start": ["B", "A"], "A": ["End"], "B": ["End"], "End": []}
    assert enumerate_paths(graph, "Start").paths == [["Start", "B", "End"], ["Start", "A", "End"]]


def test_enumerate_single_passage_story():
    assert enumerate_paths({"Only": []}, "Only").paths == [["Only"]]


def test_enumerate_missing_start_is_an_error():
    with pytest.raises(GraphError, match="start passage"):
        enumerate_paths({"A": []}, "Start")


@pytest.mark.intent("AC-output-formats-9", "ADR-017")
def test_enumerate_reports_broken_link_and_does_not_treat_it_as_an_ending():
    graph = {"Start": ["Missing", "End"], "End": []}
    result = enumerate_paths(graph, "Start")
    assert result.paths == [["Start", "End"]]
    assert result.broken_links == [("Start", "Missing")]
    assert result.cycles == []


@pytest.mark.intent("AC-output-formats-9")
def test_enumerate_passage_with_only_broken_links_ends_the_path():
    result = enumerate_paths({"Start": ["Gone"]}, "Start")
    assert result.paths == [["Start"]]
    assert result.broken_links == [("Start", "Gone")]


@pytest.mark.intent("AC-output-formats-9")
def test_enumerate_reports_each_broken_link_once():
    graph = {"Start": ["A", "B"], "A": ["Gone"], "B": ["Gone"]}
    result = enumerate_paths(graph, "Start")
    assert result.broken_links == [("A", "Gone"), ("B", "Gone")]
    graph_same_source = {"Start": ["A", "A2"], "A": ["Gone"], "A2": ["A"]}
    assert enumerate_paths(graph_same_source, "Start").broken_links == [("A", "Gone")]


@pytest.mark.intent("AC-output-formats-9")
def test_enumerate_reports_cycle_and_still_reaches_the_ending():
    graph = {"Start": ["Loop"], "Loop": ["Start", "End"], "End": []}
    result = enumerate_paths(graph, "Start")
    assert result.paths == [["Start", "Loop", "End"]]
    assert result.cycles == [["Start", "Loop", "Start"]]


def test_enumerate_cycle_with_no_way_out_ends_the_path():
    graph = {"Start": ["Loop"], "Loop": ["Start"]}
    result = enumerate_paths(graph, "Start")
    assert result.paths == [["Start", "Loop"]]
    assert result.cycles == [["Start", "Loop", "Start"]]


def test_enumerate_same_passage_on_two_branches_is_not_a_cycle():
    graph = {"Start": ["A", "B"], "A": ["Shared"], "B": ["Shared"], "Shared": []}
    result = enumerate_paths(graph, "Start")
    assert result.paths == [["Start", "A", "Shared"], ["Start", "B", "Shared"]]
    assert result.cycles == []


@pytest.mark.intent("AC-output-formats-17", "ADR-017")
def test_path_hash_is_md5_of_name_and_text_lines():
    content = {"Start": "Welcome", "End": "Bye"}
    expected = hashlib.md5(b"Start:Welcome\nEnd:Bye").hexdigest()[:8]
    assert path_hash(["Start", "End"], content) == expected


@pytest.mark.intent("AC-output-formats-17")
def test_path_hash_changes_with_content_and_structure():
    base = path_hash(["Start", "End"], {"Start": "Original", "End": "End"})
    assert path_hash(["Start", "End"], {"Start": "Modified", "End": "End"}) != base
    assert path_hash(["Start", "Mid", "End"], {"Start": "Original", "Mid": "M", "End": "End"}) != base


def test_path_hash_missing_passage_is_marked():
    assert path_hash(["Gone"], {}) == hashlib.md5(b"Gone:MISSING").hexdigest()[:8]


def test_route_hash_depends_on_names_only():
    assert route_hash(["Start", "Middle", "End"]) == hashlib.md5("Start → Middle → End".encode()).hexdigest()[:8]
    assert route_hash(["Start", "End"]) != route_hash(["Start", "Middle", "End"])
