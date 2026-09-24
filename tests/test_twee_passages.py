"""Tests for ``nanoif.twee.passages`` (the passages_deduplicated artifact)."""

import hashlib

from nanoif.schemas.artifacts import validate_artifact
from nanoif.twee.passages import content_hash, extract_passages


def test_content_hash_is_sha256_prefix():
    assert content_hash("Same content") == hashlib.sha256(b"Same content").hexdigest()[:16]
    assert len(content_hash("")) == 16


def test_extract_passages_flattens_sorted_by_name():
    story_graph = {
        "passages": {
            "Zebra": {"content": "Z", "links": []},
            "Apple": {"content": "A", "links": ["Zebra"]},
            "Middle": {"content": "M", "links": []},
        },
        "start_passage": "Apple",
        "metadata": {"story_title": "T", "ifid": "", "format": "F", "format_version": "1"},
    }
    result = extract_passages(story_graph)
    assert [p["name"] for p in result["passages"]] == ["Apple", "Middle", "Zebra"]
    assert result["passages"][0] == {"name": "Apple", "content": "A", "content_hash": content_hash("A")}
    validate_artifact(result, "passages_deduplicated")


def test_extract_passages_same_content_same_hash_different_content_different_hash():
    story_graph = {
        "passages": {
            "P1": {"content": "Same content", "links": []},
            "P2": {"content": "Same content", "links": []},
            "P3": {"content": "Other content", "links": []},
        },
        "start_passage": "P1",
        "metadata": {},
    }
    hashes = {p["name"]: p["content_hash"] for p in extract_passages(story_graph)["passages"]}
    assert hashes["P1"] == hashes["P2"] != hashes["P3"]


def test_extract_passages_empty_story():
    assert extract_passages({"passages": {}, "start_passage": "Start", "metadata": {}}) == {
        "passages": []
    }
