"""Tests for the passage index page and the file-naming helpers it uses."""

import json
from datetime import datetime

import pytest

from nanoif.cli import main
from nanoif.errors import BuildError
from nanoif.formats.passages import build_passages, passage_rows
from nanoif.twee.files import ProseFileName, parse_prose_file_name, passage_locations
from nanoif.twee.parse import parse_twee_dir


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("AB-20261101.twee", ProseFileName("AB", "2026-11-01")),
        ("AB-20261101", ProseFileName("AB", "2026-11-01")),
        ("cde-20261130.twee", ProseFileName("cde", "2026-11-30")),
        ("AB-20261131.twee", None),
        ("AB-261101.twee", None),
        ("Start.twee", None),
        ("A B-20261101.twee", None),
    ],
)
def test_parse_prose_file_name(name, expected):
    assert parse_prose_file_name(name) == expected


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def story(tmp_path):
    src = tmp_path / "src"
    write(src / "StoryData.twee", ':: StoryData\n{"ifid": "X", "start": "Start"}\n')
    write(src / "StoryTitle.twee", ":: StoryTitle\nIndex Story\n")
    write(src / "Start.twee", ":: Start\n\nBegin [[Day 1 AB]] or [[the <b>bold</b> path->Day 2 CD]]\n")
    write(src / "AB-20261101.twee", ":: Day 1 AB\n\nMorning walk.\n\n[[Market]]\n\n:: Market [ending]\n\nStalls.\n")
    write(src / "CD-20261102.twee", ":: Notes first\n\nA prologue. [[Day 2 CD]]\n\n:: Day 2 CD\n\nEvening.\n")
    write(src / "legacy.twee", ":: Day 7 EF\n\nOld naming. [[Market]]\n")
    graph = parse_twee_dir(src)
    write(tmp_path / "lib" / "artifacts" / "story_graph.json", json.dumps(graph))
    return tmp_path


def test_rows_sorted_by_file_then_line_with_inferred_writer_date_and_day(story):
    graph = parse_twee_dir(story / "src")
    rows = passage_rows(graph, passage_locations(story / "src"), story)
    assert [(r.file, r.line, r.name) for r in rows] == [
        ("src/AB-20261101.twee", 1, "Day 1 AB"),
        ("src/AB-20261101.twee", 7, "Market"),
        ("src/CD-20261102.twee", 1, "Notes first"),
        ("src/CD-20261102.twee", 5, "Day 2 CD"),
        ("src/Start.twee", 1, "Start"),
        ("src/legacy.twee", 1, "Day 7 EF"),
    ]
    by_name = {r.name: r for r in rows}
    assert (by_name["Market"].initials, by_name["Market"].date, by_name["Market"].day) == ("AB", "2026-11-01", 1)
    assert (by_name["Notes first"].initials, by_name["Notes first"].day) == ("CD", 2)
    assert (by_name["Day 7 EF"].initials, by_name["Day 7 EF"].date, by_name["Day 7 EF"].day) == ("EF", None, 7)
    assert (by_name["Start"].initials, by_name["Start"].date, by_name["Start"].day) == (None, None, None)
    assert by_name["Market"].tags == ("ending",)
    assert [r.anchor for r in rows] == ["p1", "p2", "p3", "p4", "p5", "p6"]


def test_rows_have_outgoing_and_incoming_links_and_word_counts(story):
    graph = parse_twee_dir(story / "src")
    by_name = {r.name: r for r in passage_rows(graph, passage_locations(story / "src"), story)}
    assert by_name["Start"].links_out == ("Day 1 AB", "Day 2 CD")
    assert by_name["Market"].links_in == ("Day 1 AB", "Day 7 EF")
    assert by_name["Day 2 CD"].links_in == ("Notes first", "Start")
    assert by_name["Start"].links_in == ()
    assert by_name["Day 1 AB"].words == 3
    assert by_name["Start"].words == 8


def test_build_passages_writes_escaped_filterable_page(story):
    result = build_passages(
        story / "src", story / "lib" / "artifacts" / "story_graph.json", story / "dist", datetime(2026, 11, 2, 9, 30)
    )
    assert (result.passage_count, result.file_count) == (6, 4)
    html = result.html_path.read_text()
    assert "<title>Passages - Index Story</title>" in html
    assert "6 passages in 4 files | generated 2026-11-02 09:30" in html
    assert 'id="filter"' in html and "addEventListener('input'" in html
    assert 'src/AB-20261101.twee:7' in html
    assert '<a href="#p2">Market</a>' in html
    assert html.index("Day 1 AB</td>") < html.index("Notes first</td>") < html.index("Start</td>")


def test_build_passages_missing_graph_is_an_error(story):
    with pytest.raises(BuildError, match="story_graph not found"):
        build_passages(story / "src", story / "nope.json", story / "dist")


def test_cli_build_passages(story, capsys):
    assert main(["build", "passages", "--repo", str(story)]) == 0
    assert "Passage index: 6 passages in 4 files" in capsys.readouterr().out
    assert (story / "dist" / "passages.html").exists()


def test_passage_names_are_escaped(tmp_path):
    graph = {
        "passages": {
            "Start": {"content": "Go [[<i>Fish</i> & Chips]]", "links": ["<i>Fish</i> & Chips"]},
            "<i>Fish</i> & Chips": {"content": "Salty.", "links": []},
        },
        "start_passage": "Start",
        "metadata": {"story_title": "T & <T>", "ifid": "", "format": "F", "format_version": "1"},
    }
    write(tmp_path / "graph.json", json.dumps(graph))
    html = build_passages(tmp_path / "src", tmp_path / "graph.json", tmp_path / "dist").html_path.read_text()
    assert "<i>Fish</i>" not in html
    assert "&lt;i&gt;Fish&lt;/i&gt; &amp; Chips" in html
    assert "<title>Passages - T &amp; &lt;T&gt;</title>" in html
    assert html.count("not in src/") == 2
