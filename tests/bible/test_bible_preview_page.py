"""The pull request's preview Story Bible: provisional facts and unread reasons (ADR-026)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from bible_helpers import (
    ANSWERS,
    DAY1,
    HOLLIN,
    TEXTS,
    WIDOW,
    commit,
    ent,
    scripted,
    write_cache,
    write_story,
)
from markupsafe import escape

from nanoif.bible.run import extract_bible
from nanoif.cli import main
from nanoif.formats.story_bible import StoryBibleConfig, build_story_bible
from nanoif.schemas.artifacts import validate_artifact, write_artifact

WHEN = datetime(2026, 11, 4, 9, 15)
NOW = datetime(2026, 11, 3, 7, 30, tzinfo=UTC)
NEW_WIDOW = TEXTS[WIDOW] + " Hollis Crane waited on the jetty."
WIDOW_ANSWER = {
    "summary": "Pip is eleven; Hollis waits.",
    "entities": [
        ent("Pip", [("Pip is eleven", "Eleven years old", "trait")]),
        ent("Hollis Crane", [("Hollis waits on the jetty", "Hollis Crane waited on the jetty", "event")]),
    ],
    "references": [],
}
BADGE = "from this pull request (not merged)"
CAP_REASON = "monthly AI spend cap reached: $10.00 of $10.00 in 2026-11 (resets 2026-12-01 UTC)"


@pytest.fixture
def pull_request(bible_repo):
    """``main``'s cache, then a pull request that changes The widow's door."""
    write_cache(bible_repo)
    write_story(bible_repo, {**TEXTS, WIDOW: NEW_WIDOW})
    commit(bible_repo)
    write_artifact(
        bible_repo / "dist" / "changes.json",
        {"base_ref": "main", "base_sha": "b" * 40, "changed": [WIDOW], "new": [], "removed": []},
        "changes",
    )
    return bible_repo


def extract_preview(repo, **script):
    out = repo / "preview" / "story-bible-cache.json"
    extract_bible(
        repo, "incremental", scripted({**ANSWERS, WIDOW: WIDOW_ANSWER}, **script),
        repo / "ai" / "story-bible-cache.json", True, diff_out=repo / "preview" / "bible-diff.json",
        now=NOW, preview=True, cache_out=out,
    )
    return out


def build(repo, cache, **preview):
    built = build_story_bible(
        StoryBibleConfig(
            repo_root=repo,
            cache_path=cache,
            src_dir=repo / "src",
            overrides_path=repo / "story-overrides.txt",
            story_graph_path=repo / "lib" / "artifacts" / "story_graph.json",
            output_dir=repo / "site",
            generated_at=WHEN,
            **preview,
        )
    )
    document = json.loads(built.json_path.read_text(encoding="utf-8"))
    validate_artifact(document, "story_bible")
    return built.html_path.read_text(encoding="utf-8"), document


def facts(document):
    return {f["claim"]: f for section in ("cast", "places", "items", "groups")
            for e in document[section] for f in e["facts"]}


def freshness(html):
    return html[html.index('id="freshness"'):]


@pytest.mark.intent("AC-story-bible-34", "ADR-026")
def test_the_pull_requests_facts_are_marked_and_its_passage_is_read(pull_request):
    cache = extract_preview(pull_request)
    html, document = build(pull_request, cache, preview_passages=(WIDOW,))
    shown = facts(document)
    assert shown["Hollis waits on the jetty"]["provisional"] is True
    assert shown["Pip is eleven"]["provisional"] is True
    assert "provisional" not in shown["Tam has a grey braid"]
    hollis = html[html.index("Hollis waits on the jetty"):]
    assert BADGE in hollis[: hollis.index("</li>")]
    assert "ids" in html and "merged names may change after merge" in html
    assert "conflicts" in html and "found after merge" in html
    assert escape(WIDOW) not in freshness(html)
    assert document["freshness"]["changed"] == [] and document["freshness"]["new"] == []
    assert not (pull_request / "site" / "canon-pack.json").exists()


@pytest.mark.intent("AC-story-bible-35", "ADR-026")
def test_a_passage_that_failed_is_listed_as_not_read_with_the_reason(pull_request):
    write_story(pull_request, {**TEXTS, WIDOW: NEW_WIDOW, HOLLIN: TEXTS[HOLLIN] + " He was dry."})
    commit(pull_request)
    cache = extract_preview(pull_request, fail=(WIDOW,))
    diff = json.loads((pull_request / "preview" / "bible-diff.json").read_text(encoding="utf-8"))
    html, document = build(
        pull_request, cache, preview_passages=(WIDOW, HOLLIN),
        unread_reasons={f["passage"]: f["reason"] for f in diff["passages_failed"]},
    )
    assert document["freshness"]["changed"] == [WIDOW]
    assert "LLMTransportError" in document["freshness"]["reasons"][WIDOW]
    fresh = freshness(html)
    assert escape(WIDOW) in fresh and "not read: LLMTransportError" in fresh
    assert all(not f.get("provisional") for f in facts(document).values()
               if f["passage"] == WIDOW)
    assert facts(document)["Pip is twelve"]["provisional"] is True


@pytest.mark.intent("AC-story-bible-35", "ADR-026")
def test_when_the_extraction_did_not_run_the_page_is_mains_bible_with_the_reason(pull_request):
    html, document = build(
        pull_request, pull_request / "ai" / "story-bible-cache.json", preview_passages=(WIDOW,),
        unread_reasons={WIDOW: CAP_REASON},
    )
    assert not any(f.get("provisional") for f in facts(document).values())
    assert document["freshness"]["reasons"] == {WIDOW: CAP_REASON}
    assert "resets 2026-12-01 UTC" in freshness(html)
    assert "shows the Story Bible of <code>main</code>" in html


def test_a_build_that_is_not_a_preview_is_unchanged(pull_request):
    html, document = build(pull_request, pull_request / "ai" / "story-bible-cache.json")
    assert BADGE not in html and "Pull request preview" not in html
    assert "reasons" not in document["freshness"]
    assert all("provisional" not in f for f in facts(document).values())
    assert document["freshness"]["changed"] == [WIDOW]


@pytest.mark.intent("AC-story-bible-34", "AC-story-bible-35")
def test_the_cli_builds_the_preview_page_from_the_changes_and_the_diff(pull_request, capsys):
    write_story(pull_request, {**TEXTS, WIDOW: NEW_WIDOW, DAY1: TEXTS[DAY1] + " It rained."})
    commit(pull_request)
    write_artifact(
        pull_request / "dist" / "changes.json",
        {"base_ref": "main", "base_sha": "b" * 40, "changed": [DAY1, WIDOW], "new": [],
         "removed": []},
        "changes",
    )
    cache = extract_preview(pull_request, fail=(DAY1,))
    status = main([
        "build", "story-bible", "--repo", str(pull_request), "--cache", str(cache),
        "--out", str(pull_request / "site"),
        "--preview-passages", str(pull_request / "dist" / "changes.json"),
        "--preview-diff", str(pull_request / "preview" / "bible-diff.json"),
    ])
    assert status == 0
    document = json.loads((pull_request / "site" / "story-bible.json").read_text(encoding="utf-8"))
    assert list(document["freshness"]["reasons"]) == [DAY1]
    assert "1 passage(s) not yet read" in capsys.readouterr().out
    status = main([
        "build", "story-bible", "--repo", str(pull_request), "--out", str(pull_request / "site"),
        "--preview-passages", str(pull_request / "dist" / "changes.json"),
        "--preview-reason", CAP_REASON,
    ])
    document = json.loads((pull_request / "site" / "story-bible.json").read_text(encoding="utf-8"))
    assert status == 0 and document["freshness"]["reasons"] == {DAY1: CAP_REASON, WIDOW: CAP_REASON}


@pytest.mark.parametrize("flag", [["--preview-diff", "d.json"], ["--preview-reason", "offline"]])
def test_the_cli_preview_inputs_need_the_pull_requests_passages(pull_request, flag, capsys):
    status = main(["build", "story-bible", "--repo", str(pull_request), *flag])
    assert status == 2 and "--preview-passages" in capsys.readouterr().err
