"""Per-model price table and cost estimation.

Rates are USD per million tokens. Model ids are normalized before lookup so that
provider prefixes (``accounts/fireworks/models/``) and Ollama tags (``gpt-oss:20b``)
resolve to the same row. An unknown model estimates to ``0`` with ``known=False`` so a
report can say "cost unknown" instead of "free".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _UsageLike(Protocol):
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class Rate:
    """USD per million input and output tokens."""

    input_per_m: float
    output_per_m: float


@dataclass(frozen=True)
class Estimate:
    """A cost estimate.

    Attributes:
        usd: Estimated cost in USD (``0.0`` when the model is unknown).
        known: Whether the model had a price row.
        model_key: The normalized table key that matched, or ``None``.
    """

    usd: float
    known: bool
    model_key: str | None


MODEL_RATES: dict[str, Rate] = {
    "gpt-oss-120b": Rate(0.15, 0.60),
    "gpt-oss-20b": Rate(0.07, 0.30),
    "deepseek-v4-flash": Rate(0.14, 0.28),
}

# Profiles that bill by the underlying model rate. The ``exe`` gateway serves the same
# model families as Fireworks, so its row reuses the model lookup rather than a flat rate.
PROFILE_RATE_SOURCE: dict[str, str] = {
    "exe": "model",
    "fireworks": "model",
    "ollama": "model",
    "custom": "model",
}

_PREFIXES = ("accounts/fireworks/models/", "fireworks/", "openai/", "ollama/")


def normalize_model(model: str) -> str:
    """Return the price-table key form of a model id.

    Args:
        model: Model id as sent to the provider.

    Returns:
        Lower-cased id with provider prefixes stripped and ``:`` tags folded into ``-``.
    """
    key = model.strip().lower()
    for prefix in _PREFIXES:
        if key.startswith(prefix):
            key = key[len(prefix) :]
    return key.replace(":", "-")


def rate_for(model: str, profile: str | None = None) -> tuple[Rate | None, str | None]:
    """Look up the rate for a model, honoring the profile's rate source.

    Args:
        model: Model id as sent to the provider.
        profile: Profile name; every known profile currently bills by model.

    Returns:
        ``(rate, key)`` or ``(None, None)`` when the model has no row.
    """
    source = PROFILE_RATE_SOURCE.get(profile or "exe", "model")
    if source != "model":
        return None, None
    key = normalize_model(model)
    if key in MODEL_RATES:
        return MODEL_RATES[key], key
    # Longest table key contained in the id wins (e.g. "gpt-oss-120b-fp8").
    for table_key in sorted(MODEL_RATES, key=len, reverse=True):
        if table_key in key:
            return MODEL_RATES[table_key], table_key
    return None, None


def estimate_usd(model: str, usage: _UsageLike, profile: str | None = None) -> Estimate:
    """Estimate the USD cost of one usage record.

    Args:
        model: Model id as sent to the provider.
        usage: Anything with ``prompt_tokens`` and ``completion_tokens`` attributes.
        profile: Profile name used for the rate source.

    Returns:
        The estimate; ``known`` is ``False`` and ``usd`` is ``0.0`` for an unpriced model.
    """
    rate, key = rate_for(model, profile)
    if rate is None:
        return Estimate(0.0, False, None)
    cost = usage.prompt_tokens * rate.input_per_m + usage.completion_tokens * rate.output_per_m
    usd = cost / 1e6
    return Estimate(usd, True, key)
