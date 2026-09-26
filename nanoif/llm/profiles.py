"""Inference profiles and environment-driven settings.

Every constant that names a URL, a model id, or a default limit lives here and
nowhere else. Profiles are selected with ``NANOIF_LLM_PROFILE`` and every field can be
overridden by its ``NANOIF_LLM_*`` variable.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from nanoif.llm.errors import LLMConfigError

ENV_PREFIX = "NANOIF_LLM_"

DEFAULT_PROFILE = "exe"
DEFAULT_TIMEOUT_S = 180.0
DEFAULT_MAX_RETRIES = 4
DEFAULT_MAX_CONCURRENCY = 4
DEFAULT_MAX_TOKENS_PER_JOB = 2_000_000
DEFAULT_JSON_MODE = "schema"
DEFAULT_MONTHLY_USD = 10.0
MONTHLY_CAP_OFF = "off"

JSON_MODES = ("schema", "object", "prompt")
REASONING_EFFORTS = ("minimal", "low", "medium", "high")

EXE_BASE_URL = "https://llm.int.exe.xyz/v1"
EXE_MODEL = "fireworks/glm-5p3-flash"
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
FIREWORKS_MODEL = "accounts/fireworks/models/gpt-oss-120b"
FIREWORKS_KEY_ENV = "FIREWORKS_API_KEY"
OLLAMA_BASE_URL = "http://michaels-mac-mini:11434/v1"
OLLAMA_MODEL = "gpt-oss:20b"
NO_KEY = "none"

REASONING_MODEL_MARKERS = ("gpt-oss", "deepseek-r", "deepseek-v4", "qwen3", "glm-5")
REASONING_MIN_MAX_TOKENS = 8000


@dataclass(frozen=True)
class Profile:
    """A named provider preset.

    Attributes:
        name: Profile id as given in ``NANOIF_LLM_PROFILE``.
        base_url: OpenAI-compatible base URL, or ``None`` when the env must supply it.
        api_key: Literal key, or ``None`` when the env must supply it.
        api_key_env: Extra environment variable consulted for the key.
        model: Default model id, or ``None`` when the env must supply it.
        max_concurrency: Hard cap on concurrent requests, or ``None`` for the env default.
        json_mode: Default structured-output mode for this provider.
    """

    name: str
    base_url: str | None
    api_key: str | None
    api_key_env: str | None
    model: str | None
    max_concurrency: int | None
    json_mode: str


PROFILES: dict[str, Profile] = {
    "exe": Profile("exe", EXE_BASE_URL, NO_KEY, None, EXE_MODEL, None, "schema"),
    "fireworks": Profile(
        "fireworks", FIREWORKS_BASE_URL, None, FIREWORKS_KEY_ENV, FIREWORKS_MODEL, None, "schema"
    ),
    "ollama": Profile("ollama", OLLAMA_BASE_URL, NO_KEY, None, OLLAMA_MODEL, 1, "prompt"),
    "custom": Profile("custom", None, None, None, None, None, "schema"),
}


@dataclass(frozen=True)
class Settings:
    """Effective client configuration after profile defaults and env overrides.

    Attributes:
        profile: Profile name.
        base_url: OpenAI-compatible base URL.
        api_key: API key sent as the bearer token.
        model: Model id.
        timeout_s: Per-request timeout in seconds.
        max_retries: Transport-level retries delegated to the SDK.
        max_concurrency: Maximum simultaneous requests through one client.
        reasoning_effort: Default ``reasoning_effort`` sent with every call, or ``None``.
        max_tokens_per_job: Total token budget (prompt + completion) per process.
        json_mode: ``schema`` (json_schema strict), ``object`` (json_object), or ``prompt``.
        monthly_usd: Self-imposed cap on estimated spend per UTC month (ADR-023); ``0``
            blocks all paid inference and ``None`` (``off``) disables the cap.
        ledger_dir: ``NANOIF_LLM_LEDGER_DIR`` when set (it must exist), else ``None`` for
            the default state directory.
    """

    profile: str = DEFAULT_PROFILE
    base_url: str = EXE_BASE_URL
    api_key: str = NO_KEY
    model: str = EXE_MODEL
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_retries: int = DEFAULT_MAX_RETRIES
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    reasoning_effort: str | None = None
    max_tokens_per_job: int = DEFAULT_MAX_TOKENS_PER_JOB
    json_mode: str = DEFAULT_JSON_MODE
    monthly_usd: float | None = DEFAULT_MONTHLY_USD
    ledger_dir: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from ``NANOIF_LLM_*`` variables layered over a profile.

        Args:
            env: Mapping to read; defaults to ``os.environ``.

        Returns:
            The effective settings.

        Raises:
            LLMConfigError: Unknown profile, missing required key/URL/model, or a value
                that does not parse.
        """
        env = os.environ if env is None else env
        name = env.get(f"{ENV_PREFIX}PROFILE", DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
        settings = cls.for_profile(name, env)
        return settings.with_overrides(env)

    @classmethod
    def for_profile(cls, name: str, env: Mapping[str, str] | None = None) -> Settings:
        """Return the defaults for one profile, resolving env-supplied required fields.

        Args:
            name: Profile name.
            env: Mapping used to resolve keys and required fields; defaults to ``os.environ``.

        Returns:
            Settings with the profile's defaults, before generic overrides.

        Raises:
            LLMConfigError: Unknown profile or a required field is missing.
        """
        env = os.environ if env is None else env
        try:
            profile = PROFILES[name]
        except KeyError:
            known = ", ".join(sorted(PROFILES))
            raise LLMConfigError(
                f"unknown NANOIF_LLM_PROFILE {name!r}; expected one of {known}"
            ) from None

        base_url = profile.base_url or env.get(f"{ENV_PREFIX}BASE_URL", "").strip()
        if not base_url:
            raise LLMConfigError(f"profile {name!r} needs NANOIF_LLM_BASE_URL")

        api_key = profile.api_key
        if api_key is None:
            api_key = env.get(f"{ENV_PREFIX}API_KEY", "").strip()
            if not api_key and profile.api_key_env:
                api_key = env.get(profile.api_key_env, "").strip()
            if not api_key:
                hint = f" or {profile.api_key_env}" if profile.api_key_env else ""
                raise LLMConfigError(f"profile {name!r} needs NANOIF_LLM_API_KEY{hint}")

        model = profile.model or env.get(f"{ENV_PREFIX}MODEL", "").strip()
        if not model:
            raise LLMConfigError(f"profile {name!r} needs NANOIF_LLM_MODEL")

        return cls(
            profile=name,
            base_url=base_url,
            api_key=api_key,
            model=model,
            max_concurrency=profile.max_concurrency or DEFAULT_MAX_CONCURRENCY,
            json_mode=profile.json_mode,
        )

    def with_overrides(self, env: Mapping[str, str]) -> Settings:
        """Apply generic ``NANOIF_LLM_*`` overrides on top of these settings.

        Args:
            env: Mapping to read the overrides from.

        Returns:
            A new ``Settings`` with every present variable applied.

        Raises:
            LLMConfigError: A numeric value does not parse or an enum value is unknown.
        """
        changes: dict[str, object] = {}
        for key, field in (("BASE_URL", "base_url"), ("API_KEY", "api_key"), ("MODEL", "model")):
            value = env.get(f"{ENV_PREFIX}{key}", "").strip()
            if value:
                changes[field] = value
        if timeout := env.get(f"{ENV_PREFIX}TIMEOUT_S", "").strip():
            changes["timeout_s"] = _parse_number(timeout, "TIMEOUT_S", float)
        if retries := env.get(f"{ENV_PREFIX}MAX_RETRIES", "").strip():
            changes["max_retries"] = _parse_number(retries, "MAX_RETRIES", int)
        if budget := env.get(f"{ENV_PREFIX}MAX_TOKENS_PER_JOB", "").strip():
            changes["max_tokens_per_job"] = _parse_number(budget, "MAX_TOKENS_PER_JOB", int)
        if concurrency := env.get(f"{ENV_PREFIX}MAX_CONCURRENCY", "").strip():
            requested = _parse_number(concurrency, "MAX_CONCURRENCY", int)
            cap = PROFILES[self.profile].max_concurrency
            changes["max_concurrency"] = min(requested, cap) if cap else requested
        if effort := env.get(f"{ENV_PREFIX}REASONING_EFFORT", "").strip():
            if effort not in REASONING_EFFORTS:
                raise LLMConfigError(
                    f"NANOIF_LLM_REASONING_EFFORT {effort!r} not in {REASONING_EFFORTS}"
                )
            changes["reasoning_effort"] = effort
        if mode := env.get(f"{ENV_PREFIX}JSON_MODE", "").strip():
            if mode not in JSON_MODES:
                raise LLMConfigError(f"NANOIF_LLM_JSON_MODE {mode!r} not in {JSON_MODES}")
            changes["json_mode"] = mode
        if cap := env.get(f"{ENV_PREFIX}MONTHLY_USD", "").strip():
            changes["monthly_usd"] = _parse_monthly_cap(cap)
        if ledger := env.get(f"{ENV_PREFIX}LEDGER_DIR", "").strip():
            changes["ledger_dir"] = Path(ledger).expanduser()
        settings = replace(self, **changes)  # type: ignore[arg-type]
        if settings.max_concurrency < 1:
            raise LLMConfigError("NANOIF_LLM_MAX_CONCURRENCY must be at least 1")
        if settings.max_tokens_per_job < 1:
            raise LLMConfigError("NANOIF_LLM_MAX_TOKENS_PER_JOB must be at least 1")
        if settings.timeout_s <= 0:
            raise LLMConfigError("NANOIF_LLM_TIMEOUT_S must be positive")
        if settings.max_retries < 0:
            raise LLMConfigError("NANOIF_LLM_MAX_RETRIES must not be negative")
        return settings


def is_reasoning_model(model: str) -> bool:
    """Return whether ``model`` is known to spend completion tokens on reasoning.

    Args:
        model: Model id as sent to the provider.

    Returns:
        ``True`` when the id contains a known reasoning-model marker.
    """
    lowered = model.lower()
    return any(marker in lowered for marker in REASONING_MODEL_MARKERS)


def _parse_monthly_cap(raw: str) -> float | None:
    if raw == MONTHLY_CAP_OFF:
        return None
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value < 0:
        raise LLMConfigError(
            f"NANOIF_LLM_MONTHLY_USD {raw!r} must be a non-negative number of dollars or "
            f"{MONTHLY_CAP_OFF!r}"
        )
    return value


def _parse_number(raw: str, key: str, kind: type) -> float | int:
    try:
        return kind(raw)
    except ValueError:
        raise LLMConfigError(f"NANOIF_LLM_{key} {raw!r} is not a {kind.__name__}") from None
