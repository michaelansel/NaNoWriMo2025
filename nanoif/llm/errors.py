"""Typed errors raised by the LLM client.

Every failure surfaces as one of these; no code path in ``nanoif.llm`` returns a
default-shaped success when something went wrong.
"""

from __future__ import annotations

from nanoif.errors import NanoifError


class LLMError(NanoifError):
    """Base class for every error raised by ``nanoif.llm``; a :class:`NanoifError`."""


class LLMConfigError(LLMError):
    """Settings are missing or invalid (unknown profile, absent key, bad number)."""


class LLMTransportError(LLMError):
    """The request never produced a usable completion (network, HTTP status, empty choices).

    Attributes:
        status: HTTP status code when the provider answered, else ``None``.
        body: The provider's error payload when one was returned.
    """

    def __init__(self, message: str, *, status: int | None = None, body: object = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class LLMTruncatedError(LLMError):
    """The model stopped with ``finish_reason == "length"``; the output is incomplete."""

    def __init__(self, message: str, *, text: str = "", max_tokens: int = 0) -> None:
        super().__init__(message)
        self.text = text
        self.max_tokens = max_tokens


class LLMSchemaError(LLMError):
    """The output was not valid JSON or did not satisfy the schema, after one repair round."""

    def __init__(self, message: str, *, text: str = "", errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.text = text
        self.errors = errors or []


class LLMBudgetExceeded(LLMError):
    """The per-job token budget would be exceeded by the next call."""

    def __init__(self, message: str, *, spent: int, budget: int, projected: int) -> None:
        super().__init__(message)
        self.spent = spent
        self.budget = budget
        self.projected = projected
