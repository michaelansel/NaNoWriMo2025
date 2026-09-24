"""Tests for ``nanoif.twee.files``: the header regex and passage-to-file mapping."""

from pathlib import Path

import pytest

from nanoif.twee.files import (
    PASSAGE_HEADER_RE,
    PassageLocation,
    TweePassage,
    find_twee_files,
    passage_locations,
    relative_file,
    split_twee,
)


@pytest.mark.parametrize(
    ("line", "name", "tags", "meta"),
    [
        (":: Start", "Start", None, None),
        ("::Start", "Start", None, None),
        (":: Day 1 AB", "Day 1 AB", None, None),
        (":: Start [tag1 tag2]", "Start", "tag1 tag2", None),
        ("::Middle[tagged]", "Middle", "tagged", None),
        (':: Start [footer] {"position":"100,100"}', "Start", "footer", '"position":"100,100"'),
        (':: Start {"position":"100,100"}', "Start", None, '"position":"100,100"'),
        (":: Trailing spaces   ", "Trailing spaces", None, None),
    ],
)
def test_passage_header_regex(line, name, tags, meta):
    match = PASSAGE_HEADER_RE.match(line)
    assert match is not None
    assert match.group("name").strip() == name
    assert match.group("tags") == tags
    assert match.group("meta") == meta


@pytest.mark.parametrize("line", ["Not a header", "::: Three colons", ":: [only tags]", "::"])
def test_passage_header_regex_rejects_non_headers(line):
    assert PASSAGE_HEADER_RE.match(line) is None


def test_split_twee_returns_passages_with_lines_and_tags():
    text = "Preamble\n:: Start [footer]\nHello.\n\n:: End\n\n\nBye.\n"
    assert split_twee(text) == [
        TweePassage("Start", ("footer",), "Hello.", 2, 3),
        TweePassage("End", (), "Bye.", 5, 8),
    ]


def test_split_twee_normalizes_crlf():
    assert split_twee(":: A\r\nline one\r\nline two\r\n")[0].text == "line one\nline two"


def test_split_twee_empty_passage_body():
    first = split_twee(":: A\n:: B\ntext")[0]
    assert first.text == "" and first.body_line == first.line == 1


def test_find_twee_files_is_recursive_and_sorted(tmp_path):
    (tmp_path / "b.twee").write_text(":: B\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.twee").write_text(":: A\n")
    (tmp_path / "notes.txt").write_text("ignored")
    files = find_twee_files(tmp_path)
    assert [f.relative_to(tmp_path.resolve()).as_posix() for f in files] == [
        "b.twee",
        "sub/a.twee",
    ]


def test_passage_locations_maps_names_to_file_and_line(tmp_path):
    story = tmp_path / "story.twee"
    story.write_text(":: Start\nWelcome.\n\n:: Middle [x]\nMiddle.\n")
    endings = tmp_path / "endings.twee"
    endings.write_text(":: End\nThe end.\n")
    mapping = passage_locations(tmp_path)
    assert mapping["Start"] == PassageLocation("Start", story.resolve(), 1, ())
    assert mapping["Middle"] == PassageLocation("Middle", story.resolve(), 4, ("x",))
    assert mapping["End"] == PassageLocation("End", endings.resolve(), 1, ())


def test_passage_locations_first_declaration_wins(tmp_path):
    (tmp_path / "a.twee").write_text(":: Dup\nfirst\n")
    (tmp_path / "b.twee").write_text(":: Dup\nsecond\n")
    assert passage_locations(tmp_path)["Dup"].file.name == "a.twee"


def test_passage_locations_missing_dir_is_empty(tmp_path):
    assert passage_locations(tmp_path / "nope") == {}


def test_relative_file_is_posix_relative_to_repo_root(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "AB-20251101.twee").write_text(":: Day 1 AB\nHi\n")
    location = passage_locations(src)["Day 1 AB"]
    assert relative_file(location, tmp_path) == "src/AB-20251101.twee"
    assert isinstance(location.file, Path)
