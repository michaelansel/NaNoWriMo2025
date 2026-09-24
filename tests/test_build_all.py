"""End-to-end test for ``nanoif build all`` on a throwaway repository."""

import json

from nanoif.cli import main
from nanoif.schemas.artifacts import validate_artifact
from nanoif.twee.parse import parse_twee_dir


def paperthin(repo):
    """Write the compiled story the way tweego would (no tweego needed in tests)."""
    graph = parse_twee_dir(repo / "src")
    passages = "".join(
        f'<tw-passagedata pid="{i}" name="{name}">'
        + passage["content"].replace("&", "&amp;").replace("<", "&lt;")
        + "</tw-passagedata>"
        for i, (name, passage) in enumerate(graph["passages"].items(), start=1)
    )
    html = repo / "dist" / "story-paperthin.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text(
        '<tw-storydata name="Test Story" startnode="1" ifid="ABC-123" format="Paperthin" '
        f'format-version="1.0.0">{passages}</tw-storydata>',
        encoding="utf-8",
    )


def test_build_all_runs_every_step_in_order(story_repo, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_MERGE_BASE", raising=False)
    paperthin(story_repo)
    assert main(["build", "all", "--repo", str(story_repo)]) == 0
    out = capsys.readouterr().out
    order = [
        "Parsed 5 passages",
        "Paths: 2 (new 0, modified 0, unchanged 2)",
        "Metrics:",
        "rendered the placeholder page",
        "Passage index: 5 passages",
    ]
    positions = [out.index(marker) for marker in order]
    assert positions == sorted(positions)
    dist = story_repo / "dist"
    for name in (
        "allpaths.html",
        "allpaths-index.json",
        "changes.json",
        "metrics.html",
        "story-bible.html",
        "story-bible.json",
        "passages.html",
    ):
        assert (dist / name).is_file(), name
    validate_artifact(json.loads((dist / "changes.json").read_text()), "changes")
    assert (story_repo / "lib" / "artifacts" / "story_graph.json").is_file()
    assert (story_repo / "src" / "PathIdLookup.twee").is_file()


def test_build_all_stops_at_the_first_failure(story_repo, capsys):
    assert main(["build", "all", "--repo", str(story_repo)]) == 1
    captured = capsys.readouterr()
    assert "error: compiled story not found" in captured.err
    assert not (story_repo / "dist" / "allpaths.html").exists()
