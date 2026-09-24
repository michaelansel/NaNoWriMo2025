"""Dismissal records and re-applying them when a comment is re-rendered."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from github_fakes import make_editor, make_finding, make_review

from nanoif.github.dismiss import (
    RECORD_KEYS,
    DismissalError,
    append_record,
    apply_dismissals,
    build_record,
    load_dismissals,
)

NOW = datetime(2026, 11, 3, 9, 30, tzinfo=timezone.utc)


def _review():
    return make_review(make_editor(findings=[make_finding()]), make_editor("style"))


def test_record_has_exactly_the_contract_keys_with_hashes_in_passage_order():
    record = build_record("f-1a2b3c4d", "wren-writer", 12, "on purpose", _review(), NOW)
    assert record == {
        "key": "f-1a2b3c4d",
        "passages": ["Day 1 EV", "Back at the ferry"],
        "hashes": ["h1", "h2"],
        "by": "wren-writer",
        "pr": 12,
        "at": "2026-11-03T09:30:00Z",
        "reason": "on purpose",
    }
    assert tuple(record) == RECORD_KEYS


def test_missing_reason_is_an_empty_string():
    assert build_record("f-1a2b3c4d", "w", 12, None, _review(), NOW)["reason"] == ""


def test_unknown_key_is_refused():
    with pytest.raises(DismissalError, match="f-00000000"):
        build_record("f-00000000", "wren-writer", 12, "", _review(), NOW)


def test_append_and_load_round_trip(tmp_path):
    path = tmp_path / "ai" / "dismissals.jsonl"
    path.parent.mkdir()
    path.write_text('{"key": "f-00000001"}')  # no trailing newline
    append_record(path, build_record("f-1a2b3c4d", "w", 1, "", _review(), NOW))
    lines = path.read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["key"] == "f-1a2b3c4d"
    assert [r["key"] for r in load_dismissals(path)] == ["f-00000001", "f-1a2b3c4d"]


def test_missing_file_means_no_dismissals(tmp_path):
    assert load_dismissals(tmp_path / "absent.jsonl") == []


def test_corrupt_line_is_an_error_with_its_line_number(tmp_path):
    path = tmp_path / "dismissals.jsonl"
    path.write_text('{"key": "f-00000001"}\nnot json\n')
    with pytest.raises(DismissalError, match=":2:"):
        load_dismissals(path)


@pytest.mark.intent("AC-continuity-review-12")
def test_matching_dismissal_moves_finding_to_suppressed_without_mutating_input():
    review = _review()
    record = build_record("f-1a2b3c4d", "w", 1, "", review, NOW)
    result = apply_dismissals(review, [record])
    editor = result["editors"][0]
    assert editor["findings"] == [] and [f["key"] for f in editor["suppressed"]] == ["f-1a2b3c4d"]
    assert review["editors"][0]["findings"][0]["key"] == "f-1a2b3c4d"


@pytest.mark.intent("AC-continuity-review-13")
def test_dismissal_lapses_when_a_cited_passage_changed():
    review = _review()
    record = build_record("f-1a2b3c4d", "w", 1, "", review, NOW)
    record["hashes"] = ["h1", "old-hash"]
    result = apply_dismissals(review, [record])
    assert [f["key"] for f in result["editors"][0]["findings"]] == ["f-1a2b3c4d"]


@pytest.mark.intent("AC-continuity-review-13")
def test_a_line_without_hashes_never_suppresses():
    record = {
        "key": "f-1a2b3c4d",
        "passages": [],
        "hashes": [],
        "by": "w",
        "pr": 1,
        "at": "2026-11-03T09:30:00Z",
        "reason": "",
    }
    result = apply_dismissals(_review(), [record])
    assert [f["key"] for f in result["editors"][0]["findings"]] == ["f-1a2b3c4d"]
