"""Tests for ``nanoif.graph.categorize``: base comparison and the two-level test."""

import pytest

from nanoif.git.service import GitService
from nanoif.graph.categorize import (
    BaseComparison,
    PassageChange,
    categorize_route,
    compare_graphs,
    load_base_graph,
    normalize_prose,
)
from nanoif.twee.parse import parse_twee_sources
from tests.conftest import DAY_ONE, ENDINGS, STORY_DATA, STORY_TITLE, commit_all, git

BASE_SOURCES = {"d": STORY_DATA, "t": STORY_TITLE, "one": DAY_ONE, "two": ENDINGS}
SHA = "a" * 40


def graph(**overrides):
    return parse_twee_sources({**BASE_SOURCES, **overrides})


def test_normalize_prose_ignores_links_and_whitespace():
    assert normalize_prose("Hello  world\n\n[[Link A]]") == normalize_prose("Hello world [[Link B]]")
    assert normalize_prose("Hello world") != normalize_prose("Hello there")


def test_compare_identical_graphs_marks_nothing_changed():
    comparison = compare_graphs(graph(), graph(), SHA)
    assert comparison.base_sha == SHA
    assert all(not c.changed and not c.new for c in comparison.passages.values())
    assert comparison.removed == []
    assert ("Start", "Left", "End1") in comparison.base_routes
    assert ("Start", "Right", "End2") in comparison.base_routes
    assert len(comparison.base_routes) == 2


def test_compare_detects_new_changed_and_prose_only_changes():
    head = graph(
        one=DAY_ONE.replace("You went left.", "You went left, slowly."),
        two=ENDINGS.replace("[[End2]]", "").replace(":: End2\nRight ending.", ":: End2\nRight ending.\n\n:: End3\nBonus."),
    )
    comparison = compare_graphs(head, graph(), SHA)
    assert comparison.passages["Left"] == PassageChange("Left", new=False, changed=True, prose_changed=True)
    assert comparison.passages["End3"] == PassageChange("End3", new=True, changed=True, prose_changed=True)
    assert comparison.passages["Start"] == PassageChange("Start", new=False, changed=False, prose_changed=False)


def test_compare_link_only_edit_is_changed_but_not_prose_changed():
    head = graph(one=DAY_ONE.replace("[[Go right->Right]]", "[[Go right->End2]]"))
    comparison = compare_graphs(head, graph(), SHA)
    assert comparison.passages["Start"] == PassageChange("Start", new=False, changed=True, prose_changed=False)


def test_compare_reports_removed_passages():
    head = graph(two=":: End1\nLeft ending.\n")
    assert compare_graphs(head, graph(), SHA).removed == ["End2"]


def test_compare_with_no_base_marks_everything_new():
    comparison = compare_graphs(graph(), None, SHA)
    assert all(c.new and c.changed and c.prose_changed for c in comparison.passages.values())
    assert comparison.base_routes == frozenset()


def _comparison(routes, **changes):
    passages = {
        name: PassageChange(name, *flags)
        for name, flags in {
            "Start": (False, False, False),
            "Left": (False, False, False),
            "End1": (False, False, False),
            **changes,
        }.items()
    }
    return BaseComparison(SHA, frozenset(routes), passages, [])


@pytest.mark.intent("AC-output-formats-5")
def test_categorize_route_existed_unchanged():
    assert categorize_route(["Start", "Left", "End1"], _comparison([("Start", "Left", "End1")])) == "unchanged"


@pytest.mark.intent("AC-output-formats-5", "ADR-017")
def test_categorize_route_existed_with_any_change_is_modified_never_new():
    comparison = _comparison([("Start", "Left", "End1")], End1=(False, True, True))
    assert categorize_route(["Start", "Left", "End1"], comparison) == "modified"


@pytest.mark.intent("AC-output-formats-5")
def test_categorize_new_route_with_new_passage_is_new():
    comparison = _comparison([("Start", "End1")], Left=(True, True, True))
    assert categorize_route(["Start", "Left", "End1"], comparison) == "new"


@pytest.mark.intent("AC-output-formats-5")
def test_categorize_new_route_with_changed_prose_is_new():
    comparison = _comparison([("Start", "End1")], Start=(False, True, True))
    assert categorize_route(["Start", "Left", "End1"], comparison) == "new"


@pytest.mark.intent("AC-output-formats-5", "ADR-017")
def test_categorize_new_route_with_only_link_changes_is_modified():
    comparison = _comparison([("Start", "End1")], Start=(False, True, False))
    assert categorize_route(["Start", "Left", "End1"], comparison) == "modified"


def test_categorize_unknown_passage_is_a_key_error():
    with pytest.raises(KeyError):
        categorize_route(["Start", "Nope"], _comparison([]))


def test_load_base_graph_parses_the_committed_story(story_repo):
    service = GitService(story_repo)
    first = git(story_repo, "rev-list", "--max-parents=0", "HEAD").strip()
    head_graph = load_base_graph(service, "HEAD", "src")
    assert head_graph == graph()
    first_graph = load_base_graph(service, first, "src")
    assert set(first_graph["passages"]) == {"Start", "Left", "Right"}


def test_load_base_graph_without_source_is_none(story_repo):
    (story_repo / "docs").mkdir()
    (story_repo / "docs" / "note.md").write_text("x", encoding="utf-8")
    commit_all(story_repo, "docs", "2025-11-03T10:00:00+00:00")
    assert load_base_graph(GitService(story_repo), "HEAD", "docs") is None
