"""Render the Story Bible from the extraction cache.

The cache (``story-bible-cache.json``, the 2025 v1 format) is produced
elsewhere; this module never calls a model. A missing cache is a normal state
and renders a placeholder page. A cache that exists but cannot be read is an
error: the build must not quietly publish a placeholder over real data.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from nanoif.errors import BuildError
from nanoif.formats.common import format_date_for_display, html_environment
from nanoif.git.service import GitService
from nanoif.schemas.artifacts import load_artifact, write_artifact

Facts = dict[str, Any]

CONSTANT_KEYS = ("world_rules", "setting", "timeline")
VARIABLE_KEYS = ("events", "outcomes")
CHARACTER_KEYS = ("identity", "zero_action_state", "variables")


@dataclass(frozen=True)
class StoryBibleConfig:
    """Inputs of a Story Bible build.

    Attributes:
        repo_root: The git repository root (for the source commit).
        cache_path: The extraction cache; may not exist.
        story_graph_path: ``story_graph.json`` from ``nanoif build core`` (for the title).
        passages_path: ``passages_deduplicated.json`` (for the placeholder's passage count).
        output_dir: Where ``story-bible.html`` and ``story-bible.json`` go.
        generated_at: Timestamp shown on the page; defaults to now.
    """

    repo_root: Path
    cache_path: Path
    story_graph_path: Path
    passages_path: Path
    output_dir: Path
    generated_at: datetime | None = None


@dataclass(frozen=True)
class StoryBibleResult:
    """What a Story Bible build wrote.

    Attributes:
        html_path: The page.
        json_path: The machine-readable Story Bible.
        placeholder: True when no cache existed and the placeholder was rendered.
        view_type: ``summarized``, ``per_passage`` or ``placeholder``.
        statistics: Fact counts shown on the page.
    """

    html_path: Path
    json_path: Path
    placeholder: bool
    view_type: str
    statistics: dict[str, int]


def load_cache(cache_path: Path) -> dict[str, Any] | None:
    """Read the extraction cache.

    Args:
        cache_path: The cache file.

    Returns:
        The cache, or None when the file does not exist.

    Raises:
        BuildError: If the file exists but is not a JSON object with
            ``categorized_facts``.
    """
    if not cache_path.exists():
        return None
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildError(f"Story Bible cache is unreadable: {cache_path}: {exc}") from exc
    if not isinstance(cache, dict) or not isinstance(cache.get("categorized_facts"), dict):
        raise BuildError(f"Story Bible cache has no categorized_facts object: {cache_path}")
    return cache


def select_facts(cache: Mapping[str, Any]) -> Facts:
    """Choose which fact set to render.

    Args:
        cache: A loaded cache.

    Returns:
        The summarized facts when summarization succeeded, otherwise the
        per-passage categorized facts; ``metadata.view_type`` says which.
    """
    if cache.get("summarization_status") == "success" and isinstance(
        cache.get("summarized_facts"), dict
    ):
        facts = dict(cache["summarized_facts"])
        view_type = "summarized"
    else:
        facts = dict(cache["categorized_facts"])
        view_type = "per_passage"
    metadata = dict(facts.get("metadata") or {})
    if view_type == "summarized" or "view_type" not in metadata:
        metadata["view_type"] = view_type
    facts["metadata"] = metadata
    return facts


def placeholder_facts(passage_count: int) -> Facts:
    """Return the fact set rendered when there is no cache.

    Args:
        passage_count: Passages in the story, shown on the placeholder page.

    Returns:
        Empty facts with placeholder metadata.
    """
    return {
        "constants": {},
        "variables": {},
        "characters": {},
        "conflicts": [],
        "metadata": {
            "generation_mode": "placeholder",
            "view_type": "placeholder",
            "reason": "Story Bible cache not found",
            "passages_loaded": passage_count,
            "message": "The Story Bible has not been extracted for this story yet.",
        },
    }


def normalize_evidence(evidence: Any) -> list[dict[str, str]]:
    """Normalize evidence to a list of ``{"passage", "quote"}`` objects.

    Args:
        evidence: None, a string, or a list of strings and objects.

    Returns:
        Evidence objects; strings get the passage ``"Source"``.
    """
    if evidence is None:
        return []
    items = evidence if isinstance(evidence, list) else [evidence]
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(
                {"passage": item.get("passage", "Source"), "quote": item.get("quote", str(item))}
            )
        else:
            result.append({"passage": "Source", "quote": str(item)})
    return result


def normalize_facts(facts: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Copy a fact list with each fact's evidence normalized.

    Args:
        facts: Facts, or None.

    Returns:
        The normalized facts.
    """
    return [{**fact, "evidence": normalize_evidence(fact.get("evidence"))} for fact in facts or []]


def normalize_constants(constants: Mapping[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    """Normalize ``world_rules``, ``setting`` and ``timeline``.

    Args:
        constants: The constants section, or None.

    Returns:
        The three lists normalized; empty dict for no constants.
    """
    if not constants:
        return {}
    return {key: normalize_facts(constants.get(key)) for key in CONSTANT_KEYS}


def normalize_variables(variables: Mapping[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    """Normalize ``events`` and ``outcomes``.

    Args:
        variables: The variables section, or None.

    Returns:
        The two lists normalized; empty dict for no variables.
    """
    if not variables:
        return {}
    return {key: normalize_facts(variables.get(key)) for key in VARIABLE_KEYS}


def normalize_characters(characters: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Normalize each character's fact lists, keeping ``passages`` and ``mentions``.

    Args:
        characters: Character name to its sections, or None.

    Returns:
        The normalized characters.
    """
    result: dict[str, dict[str, Any]] = {}
    for name, data in (characters or {}).items():
        entry: dict[str, Any] = {key: normalize_facts(data.get(key)) for key in CHARACTER_KEYS}
        for key in ("passages", "mentions"):
            if key in data:
                entry[key] = data[key]
        result[name] = entry
    return result


def normalize_conflicts(conflicts: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize the facts inside each conflict.

    Args:
        conflicts: Conflicts, or None.

    Returns:
        The normalized conflicts.
    """
    result = []
    for conflict in conflicts or []:
        entry = dict(conflict)
        if "facts" in conflict:
            entry["facts"] = normalize_facts(conflict["facts"])
        result.append(entry)
    return result


def calculate_statistics(
    constants: Mapping[str, list[Any]],
    characters: Mapping[str, Any],
    variables: Mapping[str, list[Any]],
) -> dict[str, int]:
    """Count facts for the page header.

    Args:
        constants: Normalized constants.
        characters: Normalized characters.
        variables: Normalized variables.

    Returns:
        ``total_constants``, ``total_variables`` and ``total_characters``.
    """
    return {
        "total_constants": sum(len(constants.get(key, [])) for key in CONSTANT_KEYS),
        "total_variables": sum(len(variables.get(key, [])) for key in VARIABLE_KEYS),
        "total_characters": len(characters),
    }


def render_html(facts: Facts, story_title: str, commit: str, generated_at: datetime) -> str:
    """Render ``story-bible.html``.

    Args:
        facts: The fact set from :func:`select_facts` or :func:`placeholder_facts`.
        story_title: Shown in the page header.
        commit: Source commit, shown abbreviated.
        generated_at: Shown as "Last Updated".

    Returns:
        The HTML page.
    """
    constants = normalize_constants(facts.get("constants"))
    characters = normalize_characters(facts.get("characters"))
    variables = normalize_variables(facts.get("variables"))
    metadata = {
        **(facts.get("metadata") or {}),
        **calculate_statistics(constants, characters, variables),
    }
    per_passage = {
        passage_id: {
            "passage_name": data.get("passage_name", "Unknown"),
            "facts": normalize_facts(data.get("facts")),
        }
        for passage_id, data in (facts.get("per_passage") or {}).items()
    }
    template = html_environment().get_template("story-bible.html.jinja2")
    return template.render(
        story_title=story_title,
        generated_at=format_date_for_display(generated_at.isoformat()),
        commit_hash=commit[:8],
        constants=constants,
        characters=characters,
        variables=variables,
        conflicts=normalize_conflicts(facts.get("conflicts")),
        per_passage=per_passage,
        metadata=metadata,
        view_type=metadata.get("view_type", "unknown"),
    )


def story_bible_document(facts: Facts, commit: str, generated_at: datetime) -> dict[str, Any]:
    """Build ``story-bible.json``.

    Args:
        facts: The fact set.
        commit: Full source commit sha.
        generated_at: Generation timestamp.

    Returns:
        The document, conforming to ``story_bible.schema.json``.
    """
    return {
        "meta": {
            "generated": generated_at.isoformat(),
            "commit": commit,
            "version": "1.0",
            "schema_version": "1.0.0",
        },
        "constants": facts.get("constants", {}),
        "characters": facts.get("characters", {}),
        "variables": facts.get("variables", {}),
        "conflicts": facts.get("conflicts", []),
        "metadata": facts.get("metadata", {}),
    }


def build_story_bible(config: StoryBibleConfig) -> StoryBibleResult:
    """Write ``story-bible.html`` and ``story-bible.json``.

    Args:
        config: Inputs; see :class:`StoryBibleConfig`.

    Returns:
        What was written.

    Raises:
        BuildError: If the cache exists but is unreadable, or a core artifact is missing.
        GitError: If the source commit cannot be resolved.
        ArtifactValidationError: If ``story-bible.json`` does not match its schema.
    """
    story_graph = load_artifact(config.story_graph_path, "story_graph")
    cache = load_cache(config.cache_path)
    if cache is None:
        passages = load_artifact(config.passages_path, "passages_deduplicated")
        facts = placeholder_facts(len(passages["passages"]))
    else:
        facts = select_facts(cache)
    commit = GitService(config.repo_root).rev_parse("HEAD")
    generated_at = config.generated_at or datetime.now()

    config.output_dir.mkdir(parents=True, exist_ok=True)
    html_path = config.output_dir / "story-bible.html"
    html_path.write_text(
        render_html(facts, story_graph["metadata"]["story_title"], commit, generated_at),
        encoding="utf-8",
    )
    json_path = config.output_dir / "story-bible.json"
    write_artifact(json_path, story_bible_document(facts, commit, generated_at), "story_bible")
    constants = normalize_constants(facts.get("constants"))
    characters = normalize_characters(facts.get("characters"))
    variables = normalize_variables(facts.get("variables"))
    return StoryBibleResult(
        html_path=html_path,
        json_path=json_path,
        placeholder=cache is None,
        view_type=facts["metadata"]["view_type"],
        statistics=calculate_statistics(constants, characters, variables),
    )
