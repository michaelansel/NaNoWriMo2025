"""Tests for artifact schema loading and write-time validation."""

import json

import pytest

from nanoif.errors import ArtifactValidationError
from nanoif.schemas.artifacts import load_schema, validate_artifact, write_artifact

GOOD_GRAPH = {
    "passages": {"Start": {"content": "Hi [[End]]", "links": ["End"]}, "End": {"content": "", "links": []}},
    "start_passage": "Start",
    "metadata": {"story_title": "T", "ifid": "X", "format": "Harlowe", "format_version": "3.3.9"},
}


def test_load_schema_reads_package_file():
    assert load_schema("story_graph")["title"] == "Story Graph"
    with pytest.raises(FileNotFoundError):
        load_schema("no_such_artifact")


def test_validate_artifact_accepts_conforming_graph():
    validate_artifact(GOOD_GRAPH, "story_graph")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda g: g.pop("start_passage"),
        lambda g: g["passages"].clear(),
        lambda g: g["passages"]["Start"].update(links=["End", "End"]),
        lambda g: g["passages"]["Start"].update(extra=1),
        lambda g: g["metadata"].pop("ifid"),
        lambda g: g.update(unexpected=True),
    ],
)
def test_validate_artifact_rejects_bad_graph(mutate):
    graph = json.loads(json.dumps(GOOD_GRAPH))
    mutate(graph)
    with pytest.raises(ArtifactValidationError, match="story_graph"):
        validate_artifact(graph, "story_graph")


@pytest.mark.intent("ADR-015")
def test_write_artifact_validates_before_writing(tmp_path):
    target = tmp_path / "nested" / "story_graph.json"
    write_artifact(target, GOOD_GRAPH, "story_graph")
    assert json.loads(target.read_text()) == GOOD_GRAPH
    bad = tmp_path / "bad.json"
    with pytest.raises(ArtifactValidationError):
        write_artifact(bad, {"passages": {}}, "story_graph")
    assert not bad.exists()
