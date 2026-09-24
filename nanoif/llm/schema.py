"""Schema loading, JSON extraction, and validation for model output.

This is the one JSON-from-LLM parser in the package: every structured completion goes
through :func:`extract_json` and :func:`validate`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from nanoif.llm.errors import LLMConfigError, LLMSchemaError

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas" / "llm"


def load_schema(name: str, schema_dir: Path | None = None) -> dict[str, Any]:
    """Load ``<name>.schema.json`` from the package schema directory.

    Args:
        name: Schema name without the ``.schema.json`` suffix.
        schema_dir: Directory to read from; defaults to ``nanoif/schemas/llm``.

    Returns:
        The parsed schema.

    Raises:
        LLMConfigError: The file is missing, unreadable, not JSON, or not a valid schema.
    """
    path = (schema_dir or SCHEMA_DIR) / f"{name}.schema.json"
    if not path.is_file():
        raise LLMConfigError(f"schema {name!r} not found at {path}")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LLMConfigError(f"schema {path} could not be read: {exc}") from exc
    if not isinstance(schema, dict):
        raise LLMConfigError(f"schema {path} must be a JSON object")
    try:
        Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise LLMConfigError(f"schema {path} is not a valid JSON Schema: {exc.message}") from exc
    return schema


def extract_json(text: str) -> Any:
    """Parse the first JSON object found in model output.

    Handles output wrapped in Markdown code fences or preceded by prose.

    Args:
        text: Raw completion text.

    Returns:
        The decoded object.

    Raises:
        LLMSchemaError: No JSON object could be decoded from the text.
    """
    if not text or not text.strip():
        raise LLMSchemaError("model returned empty output", text=text)
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        candidate = candidate.rsplit("```", 1)[0]
    decoder = json.JSONDecoder()
    start = candidate.find("{")
    while start != -1:
        try:
            value, _end = decoder.raw_decode(candidate, start)
        except json.JSONDecodeError:
            start = candidate.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return value
        start = candidate.find("{", start + 1)
    snippet = candidate[:120].replace("\n", " ")
    raise LLMSchemaError(f"no JSON object in model output: {snippet!r}", text=text)


def validate(data: Any, schema: dict[str, Any]) -> None:
    """Validate ``data`` against ``schema``.

    Args:
        data: Decoded model output.
        schema: JSON Schema (draft 2020-12).

    Raises:
        LLMSchemaError: One or more violations; the message lists each with its JSON path.
    """
    validator = Draft202012Validator(schema)
    problems = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if not problems:
        return
    lines = []
    for problem in problems:
        location = "/".join(str(part) for part in problem.absolute_path) or "(root)"
        lines.append(f"{location}: {problem.message}")
    summary = "; ".join(lines[:5])
    if len(lines) > 5:
        summary += f"; and {len(lines) - 5} more"
    raise LLMSchemaError(f"output violates schema: {summary}", errors=lines)
