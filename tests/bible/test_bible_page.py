"""The Story Bible page and story-bible.json, rendered from cache v2 with no model."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from bible_helpers import (
    CROSSING,
    DAY1,
    HOLLIN,
    TEXTS,
    WIDOW,
    clone,
    small_cache,
    write_cache,
    write_story,
)
from markupsafe import escape

from nanoif.cli import main
from nanoif.errors import BibleCacheError, BuildError
from nanoif.formats.story_bible import StoryBibleConfig, build_story_bible
from nanoif.schemas.artifacts import validate_artifact
from tests.conftest import git

WHEN = datetime(2026, 11, 4, 9, 15)


def config(repo, result="success"):
    return StoryBibleConfig(
        repo_root=repo,
        cache_path=repo / "ai" / "story-bible-cache.json",
        src_dir=repo / "src",
        overrides_path=repo / "story-overrides.txt",
        story_graph_path=repo / "lib" / "artifacts" / "story_graph.json",
        output_dir=repo / "dist",
        extraction_result=result,
        generated_at=WHEN,
    )


def page(repo, result="success"):
    built = build_story_bible(config(repo, result))
    document = json.loads(built.json_path.read_text(encoding="utf-8"))
    validate_artifact(document, "story_bible")
    return built, built.html_path.read_text(encoding="utf-8"), document


@pytest.mark.intent("AC-story-bible-1", "AC-story-bible-3")
def test_without_a_cache_the_page_is_a_placeholder_with_the_passage_count(bible_repo):
    built, html, document = page(bible_repo)
    assert built.placeholder
    assert "Placeholder Story Bible" in html and "The story has 4 passages" in html
    assert "<title>Story Bible - The Lantern Crossing</title>" in html
    head = git(bible_repo, "rev-parse", "HEAD").strip()
    assert f"Built from commit <span class=\"id\">{head[:8]}</span> on 2026-11-04 09:15 UTC" in html
    assert document["meta"]["commit"] == head and document["cache_present"] is False


@pytest.mark.intent("AC-story-bible-2")
@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        json.dumps({"categorized_facts": {}}),
        json.dumps({**small_cache(), "version": 1}),
        json.dumps({**small_cache(), "entities": []}),
        json.dumps({**small_cache(), "resolution": {"wren": "wren-halloway"}}),
    ],
)
def test_an_unusable_cache_fails_and_leaves_the_last_good_page(bible_repo, content):
    (bible_repo / "dist").mkdir()
    (bible_repo / "dist" / "story-bible.html").write_text("last good page", encoding="utf-8")
    path = bible_repo / "ai" / "story-bible-cache.json"
    path.parent.mkdir()
    path.write_text(content, encoding="utf-8")
    with pytest.raises(BibleCacheError) as info:
        build_story_bible(config(bible_repo))
    assert isinstance(info.value, BuildError)
    assert (bible_repo / "dist" / "story-bible.html").read_text(encoding="utf-8") == "last good page"
    assert not (bible_repo / "dist" / "story-bible.json").exists()


@pytest.mark.intent("AC-story-bible-5")
def test_sections_appear_in_order(bible_repo):
    write_cache(bible_repo)
    _, html, _ = page(bible_repo)
    ids = ["cast", "places", "items", "groups", "world-rules", "conflicts",
           "intentional-mysteries", "freshness"]
    positions = [html.index(f'<section class="panel" id="{name}">') for name in ids]
    assert positions == sorted(positions)
    headings = ["Cast", "Places", "Items", "Groups", "World rules", "Conflicts",
                "Intentional mysteries", "Freshness"]
    assert [html.index(f"<h2>{h}</h2>") for h in headings] == sorted(
        html.index(f"<h2>{h}</h2>") for h in headings
    )


@pytest.mark.intent("AC-story-bible-6")
def test_cast_entry_shows_name_aliases_role_passage_count_and_quoted_facts(bible_repo):
    write_cache(bible_repo)
    _, html, document = page(bible_repo)
    start = html.index('id="entity-tamsin-reeve"')
    entry = html[start : html.index("</article>", start)]
    assert "<h3>Tamsin Reeve" in entry
    assert "Also called: Old Tam, Tam" in entry and "Role: ferry keeper" in entry
    assert "Appears in 2 passages" in entry
    assert "Tam has a grey braid" in entry and "<q>her grey braid</q>" in entry
    assert f"({DAY1})" in entry
    tam = next(e for e in document["cast"] if e["slug"] == "tamsin-reeve")
    assert tam["facts"][0]["quote"] == "her grey braid" and tam["passages"] == [DAY1, CROSSING]


@pytest.mark.intent("AC-story-bible-4")
def test_markup_from_the_cache_is_escaped(bible_repo):
    data = clone(small_cache())
    data["entities"]["tamsin-reeve"]["facts"][0]["claim"] = "<script>alert(1)</script>"
    data["entities"]["tamsin-reeve"]["facts"][0]["quote"] = "<b>braid</b>"
    write_cache(bible_repo, data)
    _, html, _ = page(bible_repo)
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert "<b>braid</b>" not in html and "&lt;b&gt;braid&lt;/b&gt;" in html


@pytest.mark.intent("AC-story-bible-14", "AC-story-bible-24", "AC-story-bible-26")
def test_override_edits_show_in_the_next_build_without_extraction(bible_repo):
    write_cache(bible_repo)
    _, before, _ = page(bible_repo)
    assert "Oriel Marsh" in before
    (bible_repo / "story-overrides.txt").write_text(
        "not-entity: Captain Marsh\n"
        f'pin: Pip Halloway = Pip is twelve | "Pip was twelve" @ {HOLLIN}\n'
        "intentional-conflict: c-oriel-marsh-9\n",
        encoding="utf-8",
    )
    _, after, document = page(bible_repo)
    assert 'id="entity-oriel-marsh"' not in after
    assert "quote not found" in after and "pinned" in after
    assert "unmatched</span> line 3: <code>intentional-conflict: c-oriel-marsh-9</code>" in after
    assert document["unmatched_overrides"] == [{"line": 3, "text": "intentional-conflict: c-oriel-marsh-9"}]


@pytest.mark.intent("AC-story-bible-25")
def test_intentional_conflict_is_shown_under_intentional_mysteries(bible_repo):
    write_cache(bible_repo)
    (bible_repo / "story-overrides.txt").write_text(
        "intentional-conflict: pip-age = Pip Halloway | eleven years\n", encoding="utf-8"
    )
    _, html, document = page(bible_repo)
    conflicts = html[html.index('id="conflicts"') : html.index('id="intentional-mysteries"')]
    mysteries = html[html.index('id="intentional-mysteries"') : html.index('id="freshness"')]
    assert "c-pip-halloway-1" not in conflicts and "No two established facts disagree." in conflicts
    assert "<h3>pip-age</h3>" in mysteries and "c-pip-halloway-1" in mysteries
    assert document["intentional_mysteries"][0]["conflicts"][0]["intentional"] == "pip-age"


@pytest.mark.intent("AC-story-bible-15")
def test_freshness_names_unread_and_deleted_passages(bible_repo):
    write_cache(bible_repo)
    texts = {k: v for k, v in TEXTS.items() if k != WIDOW}
    texts[HOLLIN] += " He was dry."
    texts["The toll"] = "That night, the first since leaving Saltmarrow."
    write_story(bible_repo, texts)
    _, html, document = page(bible_repo)
    fresh = html[html.index('id="freshness"') :]
    assert "Extracted from commit <span class=\"id\">aaaaaaaa</span> on 2026-11-02 08:00 UTC" in fresh
    assert "Not yet read in their current text (2)" in fresh
    assert f"<li>{HOLLIN} <span class=\"badge\">changed</span>" in fresh
    assert "<li>The toll <span class=\"badge\">new</span>" in fresh
    assert f"<li>{escape(WIDOW)}</li>" in fresh
    assert document["freshness"]["deleted"] == [WIDOW]


@pytest.mark.intent("AC-story-bible-18")
@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped"])
def test_page_says_the_latest_extraction_did_not_complete(bible_repo, result):
    write_cache(bible_repo)
    _, html, document = page(bible_repo, result)
    assert f"The latest extraction did not complete ({result})" in html
    assert "This page shows the extraction of 2026-11-02 08:00 UTC" in html
    assert document["freshness"]["extraction_result"] == result


@pytest.mark.intent("AC-story-bible-1")
def test_cli_builds_the_placeholder_page_and_an_empty_canon_pack(bible_repo, capsys):
    assert main(["build", "story-bible", "--repo", str(bible_repo)]) == 0
    assert "rendered the placeholder page" in capsys.readouterr().out
    assert main(["build", "canon-pack", "--repo", str(bible_repo)]) == 0
    pack = json.loads((bible_repo / "dist" / "canon-pack.json").read_text(encoding="utf-8"))
    assert pack["source"]["cache_present"] is False and pack["entities"] == []


def test_cli_passes_the_extraction_result_and_counts_unread_passages(bible_repo, capsys):
    write_cache(bible_repo)
    write_story(bible_repo, {**TEXTS, "The toll": "That night."})
    status = main(["build", "story-bible", "--repo", str(bible_repo), "--extraction-result", "failure"])
    out = capsys.readouterr().out
    assert status == 0
    assert "4 characters" in out or "3 characters" in out
    assert "1 passage(s) not yet read" in out and "latest extraction: failure" in out
    with pytest.raises(SystemExit) as info:
        main(["build", "story-bible", "--repo", str(bible_repo), "--extraction-result", "maybe"])
    assert info.value.code == 2


def test_cli_canon_pack_from_the_cache(bible_repo):
    write_cache(bible_repo)
    assert main(["build", "canon-pack", "--repo", str(bible_repo)]) == 0
    pack = json.loads((bible_repo / "dist" / "canon-pack.json").read_text(encoding="utf-8"))
    assert pack["source"]["cache_present"] is True
    assert {e["slug"] for e in pack["entities"]} == {"oriel-marsh", "pip-halloway", "river-wardens", "tamsin-reeve"}


def test_cli_invalid_cache_is_exit_1(bible_repo, capsys):
    write_cache(bible_repo, {"version": 1})
    assert main(["build", "story-bible", "--repo", str(bible_repo)]) == 1
    assert "not version 2" in capsys.readouterr().err
