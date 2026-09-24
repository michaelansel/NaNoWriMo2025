"""Schema loading, JSON extraction, and validation messages."""

import json

import pytest

from nanoif.llm.errors import LLMConfigError, LLMSchemaError
from nanoif.llm.schema import SCHEMA_DIR, extract_json, load_schema, validate

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "object", "required": ["name"]}},
        "count": {"type": "integer"},
    },
    "required": ["items", "count"],
    "additionalProperties": False,
}


def test_load_schema_reads_and_checks_the_file(tmp_path):
    (tmp_path / "thing.schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    assert load_schema("thing", tmp_path) == SCHEMA


def test_load_schema_errors_are_typed(tmp_path):
    with pytest.raises(LLMConfigError, match="not found"):
        load_schema("missing", tmp_path)
    (tmp_path / "bad.schema.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(LLMConfigError, match="could not be read"):
        load_schema("bad", tmp_path)
    (tmp_path / "invalid.schema.json").write_text(json.dumps({"type": 12}), encoding="utf-8")
    with pytest.raises(LLMConfigError, match="not a valid JSON Schema"):
        load_schema("invalid", tmp_path)


@pytest.mark.intent("ADR-016")
def test_default_schema_dir_is_next_to_the_prompts():
    assert SCHEMA_DIR.name == "prompts"
    for name in ("continuity", "style"):
        assert load_schema(name)["type"] == "object"


@pytest.mark.intent("ADR-016")
def test_every_prompt_has_a_sibling_schema():
    prompts = sorted(SCHEMA_DIR.glob("*.md"))
    assert prompts, "no prompt templates found"
    for prompt in prompts:
        assert prompt.with_name(prompt.stem + ".schema.json").is_file(), prompt.name


def test_truth_schema_ships_with_the_eval_package():
    from nanoif.eval import TRUTH_SCHEMA

    schema = load_schema("truth", TRUTH_SCHEMA.parent)
    assert schema["type"] == "object"
    assert "entities" in schema["required"]


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        '  {"a": 1}\n',
        '```json\n{"a": 1}\n```',
        'Here you go:\n{"a": 1}\nHope this helps.',
        '[1, 2] then {"a": 1}',
    ],
)
def test_extract_json_finds_the_first_object(text):
    assert extract_json(text) == {"a": 1}


def test_extract_json_skips_unbalanced_braces_before_a_real_object():
    assert extract_json('the {answer is {"a": {"b": 2}}') == {"a": {"b": 2}}


@pytest.mark.parametrize("text", ["", "   ", "no json here", "{broken", "[1, 2, 3]"])
def test_extract_json_failures_are_schema_errors(text):
    with pytest.raises(LLMSchemaError):
        extract_json(text)


def test_validate_passes_valid_data():
    validate({"items": [{"name": "x"}], "count": 1}, SCHEMA)


def test_validate_reports_every_violation_with_its_path():
    with pytest.raises(LLMSchemaError) as info:
        validate({"items": [{"nom": "x"}], "count": "one", "extra": 1}, SCHEMA)
    message = str(info.value)
    assert "items/0: 'name' is a required property" in message
    assert "count: 'one' is not of type 'integer'" in message
    assert "(root):" in message
    assert len(info.value.errors) == 3
