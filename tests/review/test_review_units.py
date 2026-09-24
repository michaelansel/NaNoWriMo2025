"""Review units: ancestors, dominator marking, route cover, truncation, infra exclusion."""

from pathlib import Path

import pytest

from nanoif.errors import ReviewConfigError
from nanoif.review.units import (
    BRANCH_MARK,
    DEFAULT_UNIT_BUDGET,
    REVIEW_HEADER,
    TRUNCATE_KEEP,
    ReviewStory,
    continuity_units,
    dominators,
    read_story_style,
    select_passages,
    style_unit,
    topological_order,
    unit_budget,
)
from nanoif.twee.links import UNSELECTED
from nanoif.twee.parse import parse_twee_dir

EVAL_SRC = Path(__file__).resolve().parents[1] / "fixtures" / "eval-story" / "src"


def graph_of(passages: dict[str, str], start: str = "Start") -> dict:
    """Build a story_graph dict the way the parser would."""
    from nanoif.twee.links import link_targets

    return {
        "passages": {
            name: {"content": text, "links": link_targets(text)} for name, text in passages.items()
        },
        "start_passage": start,
        "metadata": {"story_title": "T", "ifid": "", "format": "Harlowe", "format_version": "3"},
    }


DIAMOND = {
    "Start": "Wren stood at the jetty. [[Take the ferry->Ferry]] or [[Climb the hill->Hill]].",
    "Ferry": "The fog lay on the river. [[Hollin Reach]]",
    "Hill": "Brother Ilex rang the bell. [[Hollin Reach]] or [[Gull Chapel]]",
    "Gull Chapel": "The chapel was cold.",
    "Hollin Reach": "Pip waited on the jetty. [[The weir]]",
    "The weir": "The weir roared.",
    "PathIdDisplay": "<span>footer</span>",
    "Boot": "(set: $x to 1)",
}
TAGS = {"PathIdDisplay": ("footer",), "Boot": ("startup",)}


@pytest.fixture
def diamond() -> ReviewStory:
    return ReviewStory.from_graph(graph_of(DIAMOND), TAGS)


def test_infra_passages_are_never_units_or_context(diamond):
    assert "PathIdDisplay" not in diamond.content
    assert "Boot" not in diamond.content
    assert "PathIdDisplay" not in select_passages(diamond, "all")
    with pytest.raises(ReviewConfigError):
        select_passages(diamond, "passage", passage="PathIdDisplay")
    changes = {"changed": ["PathIdDisplay", "The weir"]}
    assert select_passages(diamond, "changed", changes) == ["The weir"]


def test_single_unit_has_ancestors_in_topological_order(diamond):
    units = continuity_units(diamond, "The weir")
    assert len(units) == 1
    unit = units[0]
    assert unit.kind == "full"
    names = [entry.name for entry in unit.passages]
    assert names[-1] == "The weir"
    assert set(names[:-1]) == {"Start", "Ferry", "Hill", "Hollin Reach"}
    assert names.index("Start") < names.index("Ferry") < names.index("Hollin Reach")
    assert names.index("Hill") < names.index("Hollin Reach")
    assert "Gull Chapel" not in names
    assert unit.tokens == len(unit.text) // 4
    assert unit.text.rstrip().endswith("The weir roared.")
    assert REVIEW_HEADER.format(id=diamond.ids["The weir"]) in unit.text


def test_dominator_marking_flags_only_passages_some_route_skips(diamond):
    unit = continuity_units(diamond, "The weir")[0]
    marked = {entry.name for entry in unit.passages if entry.branch_dependent}
    assert marked == {"Ferry", "Hill"}
    assert f"[PASSAGE: {diamond.ids['Ferry']} {BRANCH_MARK}]" in unit.text
    assert f"[PASSAGE: {diamond.ids['Hollin Reach']}]" in unit.text
    assert f"[PASSAGE: {diamond.ids['Start']}]" in unit.text


def test_dominators_on_the_eval_story():
    graph = parse_twee_dir(EVAL_SRC)
    story = ReviewStory.from_graph(graph)
    doms = dominators(story.graph, story.start)
    assert doms["The toll"] == {"Start", "Day 1 EV", "Day 2 EV", "The weir", "The toll"}
    unit = continuity_units(story, "The toll")[0]
    marked = {entry.name for entry in unit.passages if entry.branch_dependent}
    assert marked == {"The crossing", "Hollin Reach", "The chapel path", "The widow's door"}


def test_ids_replace_names_in_unit_text(diamond):
    text = continuity_units(diamond, "The weir")[0].text
    for name in ("Hollin Reach", "Start", "Ferry"):
        assert f"[PASSAGE: {diamond.ids[name]}" in text
    assert "[PASSAGE: Hollin Reach" not in text
    assert "->" not in text and "[[" not in text


def test_links_outside_the_unit_render_as_unselected(diamond):
    unit = continuity_units(diamond, "The weir")[0]
    hill = next(entry for entry in unit.passages if entry.name == "Hill")
    assert hill.text == f"Brother Ilex rang the bell. Hollin Reach or {UNSELECTED}"
    start = next(entry for entry in unit.passages if entry.name == "Start")
    assert start.text == "Wren stood at the jetty. Take the ferry or Climb the hill."


def test_over_budget_splits_into_covering_routes_with_unselected_choices(diamond):
    full = continuity_units(diamond, "The weir")[0]
    units = continuity_units(diamond, "The weir", budget=full.tokens - 1)
    assert [unit.kind for unit in units] == ["route", "route"]
    assert [unit.route_index for unit in units] == [1, 2]
    assert all(unit.route_count == 2 for unit in units)
    routes = [[entry.name for entry in unit.passages] for unit in units]
    assert routes == [
        ["Start", "Ferry", "Hollin Reach", "The weir"],
        ["Start", "Hill", "Hollin Reach", "The weir"],
    ]
    first_start = units[0].passages[0].text
    assert first_start == f"Wren stood at the jetty. Take the ferry or {UNSELECTED}."
    second_start = units[1].passages[0].text
    assert second_start == f"Wren stood at the jetty. {UNSELECTED} or Climb the hill."
    assert units[0].note == "route 1 of 2"
    assert units[0].tag == "continuity:The weir#1"


def _chain(length: int) -> dict[str, str]:
    passages = {}
    for index in range(length):
        name = "Start" if index == 0 else f"Step {index}"
        following = f"Step {index + 1}" if index + 1 < length else "The weir"
        passages[name] = ("The river ran on. " * 20) + f"[[{following}]]"
    passages["The weir"] = "The weir roared."
    return passages


def test_route_over_budget_keeps_last_passages_with_a_note():
    story = ReviewStory.from_graph(graph_of(_chain(20)))
    full = continuity_units(story, "The weir")[0]
    per_passage = full.tokens // 21
    units = continuity_units(story, "The weir", budget=per_passage * 15)
    assert len(units) == 1
    unit = units[0]
    assert unit.kind == "truncated"
    assert unit.omitted == 20 - TRUNCATE_KEEP
    assert len(unit.passages) == TRUNCATE_KEEP + 1
    assert unit.passages[0].name == f"Step {20 - TRUNCATE_KEEP}"
    assert unit.text.startswith("[TRUNCATED: 8 earlier passage(s)")
    assert not unit.over_budget
    assert "8 earlier passage(s) omitted for length" in unit.note


def test_unit_still_too_long_after_truncation_is_over_budget():
    story = ReviewStory.from_graph(graph_of(_chain(20)))
    units = continuity_units(story, "The weir", budget=10)
    assert len(units) == 1
    assert units[0].over_budget
    assert units[0].tokens > 10


def test_cycles_do_not_stop_ordering():
    passages = {
        "Start": "[[Loop]]",
        "Loop": "Round again. [[Start]] or [[The weir]]",
        "The weir": "The weir roared.",
    }
    story = ReviewStory.from_graph(graph_of(passages))
    unit = continuity_units(story, "The weir")[0]
    assert [entry.name for entry in unit.passages] == ["Start", "Loop", "The weir"]
    order = topological_order(story.graph, {"Start", "Loop"}, {"Start": 0, "Loop": 1})
    assert order == ["Start", "Loop"]


def test_start_passage_unit_has_no_context(diamond):
    unit = continuity_units(diamond, "Start")[0]
    assert [entry.name for entry in unit.passages] == ["Start"]


def test_style_unit_is_the_passage_alone(diamond):
    unit = style_unit(diamond, "Hollin Reach")
    assert unit.kind == "single"
    assert [entry.name for entry in unit.passages] == ["Hollin Reach"]
    assert unit.tag == "style:Hollin Reach"


def test_unit_budget_env():
    assert unit_budget({}) == DEFAULT_UNIT_BUDGET
    assert unit_budget({"NANOIF_REVIEW_UNIT_BUDGET": "500"}) == 500
    with pytest.raises(ReviewConfigError):
        unit_budget({"NANOIF_REVIEW_UNIT_BUDGET": "lots"})
    with pytest.raises(ReviewConfigError):
        unit_budget({"NANOIF_REVIEW_UNIT_BUDGET": "0"})


def test_select_passages_modes(diamond):
    assert select_passages(diamond, "all") == sorted(diamond.content)
    assert select_passages(diamond, "passage", passage="Ferry") == ["Ferry"]
    with pytest.raises(ReviewConfigError):
        select_passages(diamond, "changed", None)
    with pytest.raises(ReviewConfigError):
        select_passages(diamond, "passage")
    with pytest.raises(ReviewConfigError):
        select_passages(diamond, "everything")


def test_read_story_style(tmp_path):
    assert read_story_style(EVAL_SRC).values == {
        "perspective": "third-person",
        "protagonist": "Wren Halloway",
        "tense": "past",
    }
    (tmp_path / "StoryData.twee").write_text(':: StoryData\n{"ifid": "X"}\n', encoding="utf-8")
    missing = read_story_style(tmp_path)
    assert missing.values == {}
    assert "no storyStyle" in missing.problem
    (tmp_path / "StoryData.twee").write_text(":: StoryData\n{not json\n", encoding="utf-8")
    assert "not valid JSON" in read_story_style(tmp_path).problem
