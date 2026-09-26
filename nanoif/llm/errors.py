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


BUDGET_EXHAUSTED_REASON = "token budget exhausted"


class LLMRunHalted(LLMError):
    """The client will make no more calls in this run; ``reason`` says why, for reports.

    Attributes:
        reason: One line a reader sees as the reason units or editors did not run.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class LLMBudgetExceeded(LLMRunHalted):
    """The per-job token budget would be exceeded by the next call."""

    def __init__(self, message: str, *, spent: int, budget: int, projected: int) -> None:
        super().__init__(message, reason=BUDGET_EXHAUSTED_REASON)
        self.spent = spent
        self.budget = budget
        self.projected = projected


class LLMSpendCapReached(LLMRunHalted):
    """This month's estimated spend has reached, or the next call would pass, the cap.

    Attributes:
        month_usd: Estimated spend recorded this month when the call was refused.
        cap_usd: The monthly cap.
    """

    def __init__(self, message: str, *, reason: str, month_usd: float, cap_usd: float) -> None:
        super().__init__(message, reason=reason)
        self.month_usd = month_usd
        self.cap_usd = cap_usd


class LLMLedgerError(LLMRunHalted):
    """The spend ledger could not be read or written; no spend is ever assumed to be zero."""
