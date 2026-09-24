"""Tests for ``nanoif.formats.allpaths.render``."""

from datetime import datetime

import pytest

from nanoif.formats.allpaths.generator import PathRecord
from nanoif.formats.allpaths.render import (
    format_date_for_display,
    path_text,
    path_text_raw,
    render_html,
)

CONTENT = {
    "Start": "This is the start. [[Middle]] or [[Skip->End]]",
    "Middle": "You are in the middle. [[End]]",
    "End": "This is the end.",
}
PASSAGES = {name: {"content": text, "links": []} for name, text in CONTENT.items()}
RECORD = PathRecord(
    number=1,
    id="abc12345",
    route=("Start", "Middle", "End"),
    passage_ids=("aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc"),
    category="new",
    files=("src/AB-20251101.twee",),
    created="2025-01-15T10:00:00Z",
    modified="2025-01-16T12:30:00+02:00",
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2025-01-15T10:30:00Z", "2025-01-15 10:30 UTC"),
        ("2025-01-15T12:30:00+02:00", "2025-01-15 10:30 UTC"),
        ("2025-01-15T10:30:00", "2025-01-15 10:30 UTC"),
        ("", "Unknown"),
        (None, "Unknown"),
        ("invalid-date", "invalid-da"),
    ],
)
def test_format_date_for_display(value, expected):
    assert format_date_for_display(value) == expected


def test_path_text_with_metadata_has_header_markers_and_selected_links():
    text = path_text(RECORD, CONTENT, 3, include_metadata=True)
    lines = text.split("\n")
    assert lines[:8] == [
        "=" * 80,
        "PATH 1 of 3",
        "=" * 80,
        "Route: aaaaaaaaaaaa → bbbbbbbbbbbb → cccccccccccc",
        "Length: 3 passages",
        "Path ID: abc12345",
        "=" * 80,
        "",
    ]
    assert "[PASSAGE: aaaaaaaaaaaa]\n\nThis is the start. Middle or [unselected]\n" in text
    assert "[PASSAGE: bbbbbbbbbbbb]\n\nYou are in the middle. End\n" in text
    assert text.endswith("[PASSAGE: cccccccccccc]\n\nThis is the end.\n")
    assert "Start" not in text.replace("This is the start", "")


def test_path_text_clean_has_no_metadata():
    text = path_text(RECORD, CONTENT, 3, include_metadata=False)
    assert text == "This is the start. Middle or [unselected]\n\nYou are in the middle. End\n\nThis is the end.\n"


def test_path_text_raw_keeps_link_markup():
    text = path_text_raw(RECORD, CONTENT, 3)
    assert text.startswith("=" * 80 + "\nPATH 1 of 3\n")
    assert "[PASSAGE: aaaaaaaaaaaa]\n\nThis is the start. [[Middle]] or [[Skip->End]]\n" in text
    assert "[[End]]" in text


def test_render_html_lists_paths_with_names_dates_and_category():
    html = render_html("Test Story", [RECORD], PASSAGES, datetime(2026, 1, 2, 3, 4, 5))
    assert "<title>All Paths - Test Story</title>" in html
    assert "Generated on 2026-01-02 03:04:05" in html
    assert 'id="total-paths">1<' in html
    assert 'data-category="new"' in html
    assert 'data-created-date="2025-01-15T10:00:00Z"' in html
    assert "Created: 2025-01-15 10:00 UTC" in html and "Modified: 2025-01-16 10:30 UTC" in html
    assert "Start → Middle → End" in html
    assert "[Passage: Start]" in html
    assert "This is the start. Middle or [unselected]" in html
    assert 'href="allpaths-clean/path-abc12345.txt"' in html
    assert "validated" not in html.lower()


def test_render_html_escapes_passage_text():
    passages = {"Start": {"content": "<b>bold</b> & [[End]]", "links": ["End"]}, "End": {"content": "x", "links": []}}
    record = PathRecord(1, "deadbeef", ("Start", "End"), ("a" * 12, "b" * 12), "unchanged", (), None, None)
    html = render_html("T", [record], passages, datetime(2026, 1, 1))
    assert "&lt;b&gt;bold&lt;/b&gt; &amp; End" in html
    assert "Created: Unknown" in html


def test_render_html_empty():
    html = render_html("Empty", [], {}, datetime(2026, 1, 1))
    assert 'id="total-paths">0<' in html and "0 passages" in html
