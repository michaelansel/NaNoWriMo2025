"""End-to-end tests for ``nanoif build allpaths`` against a throwaway repository."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from nanoif.build.core import build_core
from nanoif.cli import main
from nanoif.errors import BuildError, GitError
from nanoif.formats.allpaths import AllPathsConfig, resolve_base_ref, run
from nanoif.graph.ids import passage_id_mapping
from nanoif.graph.paths import path_hash
from nanoif.schemas.artifacts import validate_artifact
from nanoif.twee.parse import parse_twee_dir
from tests.conftest import git


def write_story_graph(repo: Path) -> Path:
    """Write story_graph.json from the source tree (the parsers agree, so no tweego needed)."""
    graph = parse_twee_dir(repo / "src")
    path = repo / "lib" / "artifacts" / "story_graph.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return path


def config(repo: Path, **overrides) -> AllPathsConfig:
    defaults = {
        "repo_root": repo,
        "src_dir": repo / "src",
        "story_graph_path": repo / "lib" / "artifacts" / "story_graph.json",
        "output_dir": repo / "dist",
        "generated_at": datetime(2026, 1, 1),
    }
    return AllPathsConfig(**{**defaults, **overrides})


def test_run_writes_every_output_for_an_unchanged_story(story_repo):
    write_story_graph(story_repo)
    result = run(config(story_repo))
    dist = story_repo / "dist"
    assert result.base_sha == git(story_repo, "rev-parse", "HEAD").strip()
    assert result.counts == {"new": 0, "modified": 0, "unchanged": 2}
    assert result.broken_links == [] and result.cycles == []
    assert [list(p.route) for p in result.paths] == [["Start", "Left", "End1"], ["Start", "Right", "End2"]]
    content = {n: p["content"] for n, p in parse_twee_dir(story_repo / "src")["passages"].items()}
    ids = passage_id_mapping(content)
    for record in result.paths:
        assert record.id == path_hash(record.route, content)
        assert record.passage_ids == tuple(ids[n] for n in record.route)
        assert record.files == ("src/AB-20251101.twee", "src/AB-20251102.twee")
        assert record.created == "2025-11-02T10:00:00+00:00"
        assert record.modified == "2025-11-02T10:00:00+00:00"
        for sub in ("allpaths-clean", "allpaths-metadata", "allpaths-raw"):
            assert (dist / sub / f"path-{record.id}.txt").is_file()
    clean = (dist / "allpaths-clean" / f"path-{result.paths[0].id}.txt").read_text()
    assert clean == "Morning. Go left or [unselected]\n\nYou went left. End1\n\nLeft ending.\n"
    metadata = (dist / "allpaths-metadata" / f"path-{result.paths[0].id}.txt").read_text()
    assert "PATH 1 of 2" in metadata and f"[PASSAGE: {ids['Start']}]" in metadata and "Start" not in metadata.replace("Path ID", "")
    raw = (dist / "allpaths-raw" / f"path-{result.paths[0].id}.txt").read_text()
    assert "[[Go left->Left]]" in raw and f"[PASSAGE: {ids['Left']}]" in raw
    mapping = json.loads((dist / "allpaths-passage-mapping.json").read_text())
    assert mapping["name_to_id"] == ids and mapping["id_to_name"][ids["Start"]] == "Start"
    assert "Test Story" in result.html_path.read_text()
    assert not (story_repo / "allpaths-validation-status.json").exists()


def test_run_index_and_changes_match_their_schemas_and_the_diff(story_repo):
    (story_repo / "src" / "AB-20251102.twee").write_text(
        ":: End1\nLeft ending, revised.\n\n:: End2\nRight ending. [[Bonus]]\n\n:: Bonus\nAn extra scene.\n",
        encoding="utf-8",
    )
    write_story_graph(story_repo)
    result = run(config(story_repo))
    dist = story_repo / "dist"
    index = json.loads((dist / "allpaths-index.json").read_text())
    validate_artifact(index, "allpaths_index")
    changes = json.loads((dist / "changes.json").read_text())
    validate_artifact(changes, "changes")

    assert changes == {
        "base_ref": "HEAD",
        "base_sha": result.base_sha,
        "changed": ["Bonus", "End1", "End2"],
        "new": ["Bonus"],
        "removed": [],
    }
    by_route = {tuple(p["route"]): p for p in index["paths"]}
    assert by_route[("Start", "Left", "End1")]["category"] == "modified"
    assert by_route[("Start", "Right", "End2", "Bonus")]["category"] == "new"
    assert result.counts == {"new": 1, "modified": 1, "unchanged": 0}
    assert index["base_sha"] == result.base_sha and index["story_title"] == "Test Story"
    passages = {p["name"]: p for p in index["passages"]}
    assert passages["Bonus"] == {
        "name": "Bonus",
        "id": passage_id_mapping(["Bonus"])["Bonus"],
        "file": "src/AB-20251102.twee",
        "changed_vs_base": True,
        "new_vs_base": True,
    }
    assert passages["Start"]["changed_vs_base"] is False and passages["Start"]["new_vs_base"] is False
    assert index["broken_links"] == [] and index["cycles"] == []
    for path in index["paths"]:
        assert path["files"] == ["src/AB-20251101.twee", "src/AB-20251102.twee"]
        assert path["created"] == "2025-11-02T10:00:00+00:00"


def test_run_uncommitted_file_has_no_dates(story_repo):
    (story_repo / "src" / "AB-20251103.twee").write_text(":: End3\nNew ending.\n", encoding="utf-8")
    (story_repo / "src" / "AB-20251101.twee").write_text(
        ":: Start\nMorning. [[End3]]\n\n:: Left\nx\n\n:: Right\ny\n", encoding="utf-8"
    )
    write_story_graph(story_repo)
    result = run(config(story_repo))
    assert [list(p.route) for p in result.paths] == [["Start", "End3"]]
    record = result.paths[0]
    assert record.files == ("src/AB-20251101.twee", "src/AB-20251103.twee")
    assert record.created == "2025-11-01T10:00:00+00:00" and record.modified == "2025-11-01T10:00:00+00:00"
    assert record.category == "new"
    index = json.loads((story_repo / "dist" / "allpaths-index.json").read_text())
    validate_artifact(index, "allpaths_index")


def test_run_reports_broken_links_and_cycles(story_repo):
    (story_repo / "src" / "AB-20251102.twee").write_text(
        ":: End1\nLeft ending. [[Nowhere]]\n\n:: End2\nRight ending. [[Start]]\n", encoding="utf-8"
    )
    write_story_graph(story_repo)
    result = run(config(story_repo))
    assert result.broken_links == [("End1", "Nowhere")]
    assert result.cycles == [["Start", "Right", "End2", "Start"]]
    assert [list(p.route) for p in result.paths] == [["Start", "Left", "End1"], ["Start", "Right", "End2"]]
    index = json.loads((story_repo / "dist" / "allpaths-index.json").read_text())
    assert index["broken_links"] == [{"from": "End1", "to": "Nowhere"}]
    assert index["cycles"] == [["Start", "Right", "End2", "Start"]]


def test_run_categorizes_against_an_explicit_base_ref(story_repo):
    first = git(story_repo, "rev-list", "--max-parents=0", "HEAD").strip()
    write_story_graph(story_repo)
    result = run(config(story_repo, base_ref=first))
    assert result.base_sha == first
    assert result.counts == {"new": 2, "modified": 0, "unchanged": 0}
    changes = json.loads((story_repo / "dist" / "changes.json").read_text())
    assert changes["new"] == ["End1", "End2"] and changes["base_ref"] == first


def test_run_with_a_base_that_has_no_story_marks_everything_new(story_repo):
    (story_repo / "notes.md").write_text("x", encoding="utf-8")
    git(story_repo, "checkout", "-q", "--orphan", "empty")
    git(story_repo, "rm", "-rq", "--cached", ".")
    git(story_repo, "add", "notes.md")
    git(story_repo, "commit", "-q", "-m", "empty base")
    write_story_graph(story_repo)
    result = run(config(story_repo))
    assert result.counts == {"new": 2, "modified": 0, "unchanged": 0}
    assert all(change.new for change in result.comparison.passages.values())


def test_run_removes_stale_path_files(story_repo):
    write_story_graph(story_repo)
    stale = story_repo / "dist" / "allpaths-clean" / "path-00000000.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")
    run(config(story_repo))
    assert not stale.exists()
    assert len(list(stale.parent.glob("path-*.txt"))) == 2


def test_run_unresolvable_base_ref_is_an_error(story_repo):
    write_story_graph(story_repo)
    with pytest.raises(GitError):
        run(config(story_repo, base_ref="origin/does-not-exist"))


def test_run_missing_story_graph_is_an_error(story_repo):
    with pytest.raises(BuildError, match="story_graph not found"):
        run(config(story_repo))


def test_run_stale_story_graph_is_an_error(story_repo):
    write_story_graph(story_repo)
    (story_repo / "src" / "AB-20251102.twee").write_text(":: End1\nonly\n", encoding="utf-8")
    with pytest.raises(BuildError, match="End2"):
        run(config(story_repo))


def test_run_src_outside_repo_is_an_error(story_repo, tmp_path):
    write_story_graph(story_repo)
    with pytest.raises(BuildError, match="not inside"):
        run(config(story_repo, src_dir=tmp_path))


def test_resolve_base_ref_env_contract():
    assert resolve_base_ref({}) == "HEAD"
    assert resolve_base_ref({"GITHUB_MERGE_BASE": "abc123", "GITHUB_BASE_REF": "main"}) == "abc123"
    assert resolve_base_ref({"GITHUB_MERGE_BASE": "abc123"}) == "abc123"
    with pytest.raises(BuildError, match="GITHUB_MERGE_BASE"):
        resolve_base_ref({"GITHUB_BASE_REF": "main"})
    with pytest.raises(BuildError):
        resolve_base_ref({"GITHUB_BASE_REF": "main", "GITHUB_MERGE_BASE": "  "})


def test_cli_build_allpaths_after_build_core(story_repo, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_MERGE_BASE", raising=False)
    (story_repo / "src" / "AB-20251102.twee").write_text(
        ":: End1\nLeft ending. [[Gone]]\n\n:: End2\nRight ending.\n", encoding="utf-8"
    )
    html = story_repo / "dist" / "story-paperthin.html"
    html.parent.mkdir()
    graph = parse_twee_dir(story_repo / "src")
    html.write_text(
        '<tw-storydata name="Test Story" startnode="1" ifid="ABC-123" format="Paperthin" format-version="1.0.0">'
        + "".join(
            f'<tw-passagedata pid="{i}" name="{n}">{p["content"].replace("<", "&lt;")}</tw-passagedata>'
            for i, (n, p) in enumerate(graph["passages"].items(), start=1)
        )
        + "</tw-storydata>",
        encoding="utf-8",
    )
    build_core(html, story_repo / "src", story_repo / "lib" / "artifacts", story_repo / "src" / "PathIdLookup.twee")
    argv = [
        "build",
        "allpaths",
        "--repo",
        str(story_repo),
    ]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "Base ref: HEAD (" in out
    assert "Paths: 2 (new 0, modified 1, unchanged 1)" in out
    assert "WARNING: broken link 'End1' -> 'Gone' (not followed)" in out
    assert (story_repo / "dist" / "allpaths-index.json").exists()


def test_cli_build_allpaths_bad_base_ref_reports_error(story_repo, capsys):
    write_story_graph(story_repo)
    argv = [
        "build", "allpaths",
        "--repo", str(story_repo),
        "--base-ref", "nope",
    ]
    assert main(argv) == 1
    assert "error: git rev-parse" in capsys.readouterr().err
