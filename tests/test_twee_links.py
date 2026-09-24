"""Tests for the one link parser, ``nanoif.twee.links``."""

import pytest

from nanoif.twee.links import (
    UNSELECTED,
    Link,
    display_text,
    find_links,
    link_targets,
    split_link,
    strip_links,
)


@pytest.mark.intent("AC-web-editing-4")
@pytest.mark.parametrize(
    ("inner", "expected"),
    [
        ("Target", ("Target", "Target")),
        ("Another Passage", ("Another Passage", "Another Passage")),
        ("Display->Target", ("Display", "Target")),
        ("Target<-Display", ("Display", "Target")),
        ("Text|Target", ("Text", "Target")),
        ("  padded  ->  Target  ", ("padded", "Target")),
        # rightmost -> separates, so text may contain an arrow
        ("A->B->C", ("A->B", "C")),
        # leftmost <- separates
        ("A<-B<-C", ("B<-C", "A")),
        ("A|B|C", ("A|B", "C")),
    ],
)
def test_split_link(inner, expected):
    assert split_link(inner) == expected


def test_find_links_reports_spans_in_document_order():
    text = "Go [[North]] or [[east->Eastern Path]] now"
    links = find_links(text)
    assert links == [
        Link("North", "North", 3, 12),
        Link("east", "Eastern Path", 16, 38),
    ]
    assert text[links[1].start : links[1].end] == "[[east->Eastern Path]]"


def test_find_links_allows_close_bracket_inside_text():
    links = find_links("Pick [[the box [red]->Red Box]] please")
    assert [(link.text, link.target) for link in links] == [("the box [red]", "Red Box")]


@pytest.mark.intent("AC-web-editing-5")
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('(link-goto: "Open the door", "Hallway")', [("Open the door", "Hallway")]),
        ("(link-goto: 'Hallway')", [("Hallway", "Hallway")]),
        ('(link-reveal-goto: "More", "Next")', [("More", "Next")]),
        ('(click-goto: "word", "Next")', [("word", "Next")]),
        ('(goto: "Next")', [("", "Next")]),
        ('(LINK-GOTO:"a" , "Spaced Args")', [("a", "Spaced Args")]),
        ('(link-goto: "Say \\"hi\\"", "Quoted")', [('Say "hi"', "Quoted")]),
    ],
)
def test_find_links_harlowe_macros(text, expected):
    assert [(link.text, link.target) for link in find_links(text)] == expected


def test_link_targets_are_unique_in_order():
    text = "[[B]] then [[A]] then [[again->B]] and (link-goto: 'C')"
    assert link_targets(text) == ["B", "A", "C"]


def test_link_targets_none():
    assert link_targets("This has no links at all") == []


def test_link_targets_ignores_single_bracket_text():
    assert link_targets("A [note] and an array[0] and [[Real]]") == ["Real"]


def test_strip_links_removes_markup_and_text():
    result = strip_links("Some text [[Target]] more text [[Display->Other]] end")
    assert "[[" not in result and "Target" not in result and "Display" not in result
    assert result == "Some text  more text  end"


def test_strip_links_same_prose_different_links_matches():
    assert strip_links("Hello world\n\n[[Link A]]") == strip_links("Hello world\n\n[[Link B]]")


def test_display_text_without_selection_shows_all_text():
    assert display_text("You can [[Continue->Next]] or [[GoBack]].") == "You can Continue or GoBack."


def test_display_text_marks_unselected_when_several_links():
    text = "It's [[sunny->Day 30 AB]] or [[raining]]."
    assert display_text(text, "raining") == f"It's {UNSELECTED} or raining."
    assert display_text(text, "Day 30 AB") == f"It's sunny or {UNSELECTED}."


def test_display_text_removes_only_link_when_not_selected():
    assert display_text("Go [[on->Next]] now", "Elsewhere") == "Go  now"


def test_display_text_shows_every_link_to_selected_target():
    text = "[[left->Room]] or [[right->Room]]"
    assert display_text(text, "Room") == "left or right"


def test_display_text_renders_macros_as_prose():
    text = 'Then (link-goto: "open the door", "Hallway") or [[wait]].'
    assert display_text(text, "Hallway") == f"Then open the door or {UNSELECTED}."


def test_display_text_accepts_several_selected_targets():
    text = "Take [[the ferry->Crossing]], [[the hill->Chapel]] or [[stay]]."
    assert display_text(text, {"Crossing", "Chapel"}) == f"Take the ferry, the hill or {UNSELECTED}."


def test_display_text_empty_selection_marks_every_link():
    text = "Take [[the ferry->Crossing]] or [[the hill->Chapel]]."
    assert display_text(text, set()) == f"Take {UNSELECTED} or {UNSELECTED}."
