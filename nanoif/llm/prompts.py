"""Render the Jinja prompts (editors and Story Bible) into system and user messages.

Each prompt is ``nanoif/prompts/<name>.md`` with a ``system`` block (rules and rubric) and
a ``user`` block (story text between delimiters), beside ``<name>.schema.json`` for the
structured output. Python holds no prompt text.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined

from nanoif.llm.schema import load_schema

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

_ENV = Environment(
    loader=PackageLoader("nanoif", "prompts"),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
)


@dataclass(frozen=True)
class Prompt:
    """A rendered prompt.

    Attributes:
        system: The system message: role, rules, rubric, output instructions.
        user: The user message: the story text between delimiters.
    """

    system: str
    user: str


def render_prompt(name: str, **context: Any) -> Prompt:
    """Render ``nanoif/prompts/<name>.md``.

    Args:
        name: Prompt name, for example ``"continuity"``.
        **context: Template variables; a missing one is an error (``StrictUndefined``).

    Returns:
        The system and user messages, stripped.

    Raises:
        jinja2.TemplateNotFound: No such prompt.
        jinja2.UndefinedError: A variable the template uses was not given.
    """
    template = _ENV.get_template(f"{name}.md")
    parts = {}
    for block in ("system", "user"):
        rendered = "".join(template.blocks[block](template.new_context(dict(context))))
        parts[block] = rendered.strip()
    return Prompt(system=parts["system"], user=parts["user"])


@cache
def prompt_schema(name: str) -> dict[str, Any]:
    """Load the structured-output schema that sits beside a prompt.

    Args:
        name: Prompt name.

    Returns:
        The parsed schema.

    Raises:
        LLMConfigError: The schema is missing or invalid.
    """
    return load_schema(name, PROMPTS_DIR)


def prompt_hash(name: str) -> str:
    """Return the first 12 hex digits of the SHA-256 of a prompt template file.

    Recorded with every Story Bible extraction, so a cache says which prompts produced it.

    Args:
        name: Prompt name.

    Returns:
        12 lower-case hex digits.

    Raises:
        FileNotFoundError: No such prompt.
    """
    return hashlib.sha256((PROMPTS_DIR / f"{name}.md").read_bytes()).hexdigest()[:12]
