"""Tests for ``nanoif.formats.story_bible``."""

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from nanoif.errors import BuildError
from nanoif.formats.story_bible import (
    StoryBibleConfig,
    build_story_bible,
    load_cache,
    select_facts,
)
from nanoif.formats.story_bible.render import (
    calculate_statistics,
    normalize_characters,
    normalize_conflicts,
    normalize_constants,
    normalize_evidence,
    normalize_facts,
    normalize_variables,
    placeholder_facts,
    render_html,
)
from nanoif.schemas.artifacts import validate_artifact
from nanoif.twee.parse import parse_twee_dir
from nanoif.twee.passages import extract_passages
from tests.conftest import git

WHEN = datetime(2026, 1, 2, 3, 4)
SHA = "0123456789abcdef0123456789abcdef01234567"


# --- evidence and fact normalization -------------------------------------------------


def test_normalize_evidence_forms():
    assert normalize_evidence(None) == []
    assert normalize_evidence("She cast a spell") == [{"passage": "Source", "quote": "She cast a spell"}]
    assert normalize_evidence(["one", "two"]) == [
        {"passage": "Source", "quote": "one"},
        {"passage": "Source", "quote": "two"},
    ]
    assert normalize_evidence(["plain", {"passage": "Middle", "quote": "obj"}]) == [
        {"passage": "Source", "quote": "plain"},
        {"passage": "Middle", "quote": "obj"},
    ]
    assert normalize_evidence([{"quote": "no passage"}]) == [{"passage": "Source", "quote": "no passage"}]


def test_normalize_evidence_object_without_quote_is_stringified():
    result = normalize_evidence([{"passage": "Start", "other": "data"}])
    assert result[0]["passage"] == "Start" and "other" in result[0]["quote"]


def test_normalize_facts_keeps_fields_and_normalizes_evidence():
    assert normalize_facts(None) == [] and normalize_facts([]) == []
    facts = [{"fact": "Magic exists", "type": "world_rule", "confidence": "high", "evidence": "q"}]
    assert normalize_facts(facts) == [
        {"fact": "Magic exists", "type": "world_rule", "confidence": "high", "evidence": [{"passage": "Source", "quote": "q"}]}
    ]
    assert facts[0]["evidence"] == "q"


def test_normalize_constants_and_variables():
    assert normalize_constants(None) == {} and normalize_constants({}) == {}
    constants = normalize_constants({"world_rules": [{"fact": "a", "evidence": "q"}], "setting": [{"fact": "b"}]})
    assert set(constants) == {"world_rules", "setting", "timeline"}
    assert constants["world_rules"][0]["evidence"] == [{"passage": "Source", "quote": "q"}]
    assert constants["setting"][0]["evidence"] == [] and constants["timeline"] == []
    assert normalize_variables({}) == {}
    assert set(normalize_variables({"events": [{"fact": "x"}]})) == {"events", "outcomes"}


def test_normalize_characters_keeps_passages_and_mentions():
    assert normalize_characters({}) == {}
    result = normalize_characters(
        {
            "Rowan": {
                "identity": [{"fact": "Is a student", "evidence": "q"}],
                "passages": ["AB-20251101", "CD-20251114"],
                "mentions": [{"quote": "Rowan said", "context": "dialogue", "passage": "AB-20251101"}],
            }
        }
    )
    assert set(result["Rowan"]) == {"identity", "zero_action_state", "variables", "passages", "mentions"}
    assert result["Rowan"]["passages"] == ["AB-20251101", "CD-20251114"]
    assert result["Rowan"]["mentions"][0]["context"] == "dialogue"
    assert result["Rowan"]["identity"][0]["evidence"][0]["quote"] == "q"


def test_normalize_conflicts():
    assert normalize_conflicts(None) == [] and normalize_conflicts([]) == []
    result = normalize_conflicts(
        [{"description": "Timeline", "facts": [{"fact": "10 years", "evidence": "a"}, {"fact": "2 years", "evidence": "b"}]}]
    )
    assert result[0]["description"] == "Timeline"
    assert result[0]["facts"][1]["evidence"] == [{"passage": "Source", "quote": "b"}]


def test_calculate_statistics_counts_all_sections():
    constants = normalize_constants({"world_rules": [{"fact": "r"}] * 8, "setting": [{"fact": "s"}] * 599, "timeline": [{"fact": "t"}] * 158})
    variables = normalize_variables({"events": [{"fact": "e"}] * 5, "outcomes": [{"fact": "o"}] * 3})
    characters = normalize_characters({f"Character{i}": {} for i in range(36)})
    assert calculate_statistics(constants, characters, variables) == {
        "total_constants": 765,
        "total_variables": 8,
        "total_characters": 36,
    }


# --- cache selection -----------------------------------------------------------------

CATEGORIZED = {
    "constants": {"world_rules": [{"fact": "Magic is rare", "evidence": [{"passage": "Start", "quote": "rarely"}]}]},
    "characters": {},
    "variables": {},
    "conflicts": [],
    "per_passage": {"Start": {"passage_name": "Start", "facts": [{"fact": "Per-passage fact", "evidence": "q"}]}},
}
SUMMARIZED = {
    "constants": {"setting": [{"fact": "A coastal town", "evidence": [{"passage": "Start", "quote": "the sea"}]}]},
    "characters": {"Rowan": {"identity": [{"fact": "Apprentice", "evidence": []}], "passages": ["Start"]}},
    "variables": {},
    "conflicts": [],
}


def test_select_facts_prefers_successful_summary():
    facts = select_facts({"categorized_facts": CATEGORIZED, "summarized_facts": SUMMARIZED, "summarization_status": "success"})
    assert facts["metadata"]["view_type"] == "summarized"
    assert "Rowan" in facts["characters"]


def test_select_facts_falls_back_to_per_passage():
    for status in ("failed", "not_run", None):
        facts = select_facts({"categorized_facts": CATEGORIZED, "summarized_facts": SUMMARIZED, "summarization_status": status})
        assert facts["metadata"]["view_type"] == "per_passage"
        assert "per_passage" in facts
    assert CATEGORIZED.get("metadata") is None


def test_load_cache_missing_is_none(tmp_path):
    assert load_cache(tmp_path / "story-bible-cache.json") is None


@pytest.mark.intent("AC-story-bible-2")
@pytest.mark.parametrize("content", ["{not json", "[]", '{"meta": {}}', '{"categorized_facts": []}'])
def test_load_cache_unusable_is_an_error(tmp_path, content):
    cache = tmp_path / "story-bible-cache.json"
    cache.write_text(content, encoding="utf-8")
    with pytest.raises(BuildError, match="Story Bible cache"):
        load_cache(cache)


# --- rendering -----------------------------------------------------------------------


@pytest.mark.intent("AC-story-bible-3")
def test_render_html_with_entity_data():
    facts = {
        "metadata": {"view_type": "entity_first", "generation_mode": "ai"},
        "constants": {"world_rules": [], "setting": [], "timeline": []},
        "characters": {
            "Rowan": {
                "identity": [{"fact": "Former member of the guild", "evidence": [{"passage": "AB-20251101", "quote": "when Rowan was with us"}]}],
                "passages": ["AB-20251101", "CD-20251114"],
                "mentions": [
                    {"quote": "when Rowan was with us", "context": "dialogue", "passage": "AB-20251101"},
                    {"quote": "since we lost Rowan", "context": "dialogue", "passage": "CD-20251114"},
                ],
            },
            "Tess": {"identity": [], "passages": ["Start"], "mentions": [{"quote": "Tess said", "context": "dialogue", "passage": "Start"}]},
        },
        "variables": {"events": [], "outcomes": []},
        "conflicts": [],
        "per_passage": {},
    }
    html = render_html(facts, "Test Story", SHA, WHEN)
    assert "<title>Story Bible - Test Story</title>" in html
    assert "Mentioned in 2 passages" in html and "Mentioned in 1 passage<" in html
    assert "AB-20251101" in html and "CD-20251114" in html
    assert "when Rowan was with us" in html and "dialogue" in html
    assert "Source Commit:</strong> 01234567" in html
    assert "Last Updated:</strong> 2026-01-02 03:04 UTC" in html


def test_render_html_without_passages_or_mentions():
    facts = {
        "metadata": {"view_type": "summarized"},
        "characters": {"Tess": {"identity": [{"fact": "Student at the academy", "evidence": [{"passage": "Start", "quote": "Tess studied"}]}]}},
    }
    html = render_html(facts, "T", SHA, WHEN)
    assert "Tess" in html and "Student at the academy" in html
    assert "Summarized" in html


def test_render_html_shows_statistics_from_the_data():
    facts = {
        "constants": {"world_rules": [{"fact": "r", "evidence": []}] * 8, "setting": [{"fact": "s", "evidence": []}] * 599, "timeline": [{"fact": "t", "evidence": []}] * 158},
        "characters": {f"Character{i}": {} for i in range(36)},
        "variables": {"events": [{"fact": "e", "evidence": []}] * 5, "outcomes": [{"fact": "o", "evidence": []}] * 3},
        "conflicts": [],
        "metadata": {},
    }
    html = render_html(facts, "T", SHA, WHEN)
    stats = re.search(r"(\d+)\s+constants,\s*(\d+)\s+variables,\s*(\d+)\s+characters", html)
    assert stats is not None
    assert stats.groups() == ("765", "8", "36")


@pytest.mark.intent("AC-story-bible-4")
def test_render_html_escapes_quotes_from_the_cache():
    facts = {"constants": {"setting": [{"fact": "<script>alert(1)</script>", "evidence": []}]}, "metadata": {}}
    html = render_html(facts, "T", SHA, WHEN)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_placeholder():
    html = render_html(placeholder_facts(65), "T", SHA, WHEN)
    assert "Placeholder Story Bible" in html
    assert "Loaded 65 passages" in html


# --- end to end ----------------------------------------------------------------------


def _artifacts(repo: Path) -> Path:
    graph = parse_twee_dir(repo / "src")
    artifacts = repo / "lib" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "story_graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (artifacts / "passages_deduplicated.json").write_text(json.dumps(extract_passages(graph)), encoding="utf-8")
    return artifacts


def _config(repo: Path) -> StoryBibleConfig:
    artifacts = repo / "lib" / "artifacts"
    return StoryBibleConfig(
        repo_root=repo,
        cache_path=repo / "story-bible-cache.json",
        story_graph_path=artifacts / "story_graph.json",
        passages_path=artifacts / "passages_deduplicated.json",
        output_dir=repo / "dist",
        generated_at=WHEN,
    )


@pytest.mark.intent("AC-story-bible-1", "AC-story-bible-3")
def test_build_without_cache_renders_placeholder(story_repo):
    _artifacts(story_repo)
    result = build_story_bible(_config(story_repo))
    assert result.placeholder is True and result.view_type == "placeholder"
    html = result.html_path.read_text()
    assert "Placeholder Story Bible" in html and "Loaded 5 passages" in html
    assert "<title>Story Bible - Test Story</title>" in html
    document = json.loads(result.json_path.read_text())
    validate_artifact(document, "story_bible")
    assert document["meta"]["commit"] == git(story_repo, "rev-parse", "HEAD").strip()
    assert document["metadata"]["generation_mode"] == "placeholder"


def test_build_with_cache_renders_summary(story_repo):
    _artifacts(story_repo)
    (story_repo / "story-bible-cache.json").write_text(
        json.dumps({"categorized_facts": CATEGORIZED, "summarized_facts": SUMMARIZED, "summarization_status": "success"}),
        encoding="utf-8",
    )
    result = build_story_bible(_config(story_repo))
    assert result.placeholder is False and result.view_type == "summarized"
    assert result.statistics == {"total_constants": 1, "total_variables": 0, "total_characters": 1}
    html = result.html_path.read_text()
    assert "A coastal town" in html and "Placeholder" not in html
    document = json.loads(result.json_path.read_text())
    validate_artifact(document, "story_bible")
    assert document["characters"]["Rowan"]["passages"] == ["Start"]
    assert document["meta"]["generated"] == WHEN.isoformat()


@pytest.mark.intent("AC-story-bible-2")
def test_build_with_corrupt_cache_fails(story_repo):
    _artifacts(story_repo)
    (story_repo / "story-bible-cache.json").write_text("{", encoding="utf-8")
    with pytest.raises(BuildError, match="unreadable"):
        build_story_bible(_config(story_repo))
    assert not (story_repo / "dist" / "story-bible.html").exists()


def test_build_without_core_artifacts_fails(story_repo):
    with pytest.raises(BuildError, match="story_graph not found"):
        build_story_bible(_config(story_repo))


@pytest.mark.intent("AC-story-bible-1")
def test_cli_build_story_bible(story_repo, capsys):
    from nanoif.cli import main

    _artifacts(story_repo)
    assert main(["build", "story-bible", "--repo", str(story_repo)]) == 0
    assert "rendered the placeholder page" in capsys.readouterr().out
    assert (story_repo / "dist" / "story-bible.json").exists()
