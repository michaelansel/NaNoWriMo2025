"""JSON schemas for build artifacts, and validation at write time."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema

from nanoif.errors import ArtifactValidationError

SCHEMA_DIR = Path(__file__).resolve().parent


@cache
def load_schema(name: str) -> dict[str, Any]:
    """Load an artifact schema by name.

    Args:
        name: The artifact name, for example ``"story_graph"``.

    Returns:
        The parsed schema.

    Raises:
        FileNotFoundError: If no ``<name>.schema.json`` exists in this package.
    """
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def validate_artifact(data: Any, name: str) -> None:
    """Validate an artifact against its schema.

    Args:
        data: The artifact, as it will be serialized.
        name: The artifact name, for example ``"story_graph"``.

    Raises:
        ArtifactValidationError: If the artifact does not conform.
    """
    validator = jsonschema.Draft7Validator(load_schema(name))
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        where = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise ArtifactValidationError(
            f"{name}: {len(errors)} schema violation(s); first at {where}: {first.message}"
        )


def write_artifact(path: Path, data: Any, name: str) -> None:
    """Validate an artifact and write it as indented JSON.

    Args:
        path: Destination file; parent directories are created.
        data: The artifact.
        name: The artifact name whose schema applies.

    Raises:
        ArtifactValidationError: If the artifact does not conform; nothing is written.
    """
    validate_artifact(data, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
