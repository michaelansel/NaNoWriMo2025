"""Settings resolution from profiles and NANOIF_LLM_* variables."""

import pytest

from nanoif.llm.errors import LLMConfigError
from nanoif.llm.profiles import (
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS_PER_JOB,
    DEFAULT_TIMEOUT_S,
    EXE_BASE_URL,
    FIREWORKS_BASE_URL,
    FIREWORKS_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    Settings,
    is_reasoning_model,
)


@pytest.mark.intent("ADR-016")
def test_empty_env_gives_exe_defaults():
    s = Settings.from_env({})
    assert s.profile == "exe"
    assert s.base_url == EXE_BASE_URL
    assert s.api_key == "none"
    assert s.timeout_s == DEFAULT_TIMEOUT_S == 180.0
    assert s.max_retries == DEFAULT_MAX_RETRIES == 4
    assert s.max_concurrency == DEFAULT_MAX_CONCURRENCY == 4
    assert s.max_tokens_per_job == DEFAULT_MAX_TOKENS_PER_JOB == 2_000_000
    assert s.json_mode == "schema"
    assert s.reasoning_effort is None


def test_fireworks_requires_a_key():
    with pytest.raises(LLMConfigError, match="FIREWORKS_API_KEY"):
        Settings.from_env({"NANOIF_LLM_PROFILE": "fireworks"})


def test_fireworks_reads_key_from_provider_env_or_nanoif_env():
    s = Settings.from_env({"NANOIF_LLM_PROFILE": "fireworks", "FIREWORKS_API_KEY": "fw-1"})
    assert s.api_key == "fw-1"
    assert s.base_url == FIREWORKS_BASE_URL
    assert s.model == FIREWORKS_MODEL
    s2 = Settings.from_env({"NANOIF_LLM_PROFILE": "fireworks", "NANOIF_LLM_API_KEY": "k"})
    assert s2.api_key == "k"


@pytest.mark.intent("ADR-016")
def test_ollama_forces_concurrency_one_and_prompt_json_mode():
    s = Settings.from_env({"NANOIF_LLM_PROFILE": "ollama", "NANOIF_LLM_MAX_CONCURRENCY": "8"})
    assert s.base_url == OLLAMA_BASE_URL
    assert s.model == OLLAMA_MODEL
    assert s.max_concurrency == 1
    assert s.json_mode == "prompt"
    assert s.api_key == "none"


def test_custom_requires_url_key_and_model():
    with pytest.raises(LLMConfigError, match="BASE_URL"):
        Settings.from_env({"NANOIF_LLM_PROFILE": "custom"})
    with pytest.raises(LLMConfigError, match="API_KEY"):
        Settings.from_env({"NANOIF_LLM_PROFILE": "custom", "NANOIF_LLM_BASE_URL": "http://x/v1"})
    with pytest.raises(LLMConfigError, match="MODEL"):
        Settings.from_env(
            {
                "NANOIF_LLM_PROFILE": "custom",
                "NANOIF_LLM_BASE_URL": "http://x/v1",
                "NANOIF_LLM_API_KEY": "k",
            }
        )
    s = Settings.from_env(
        {
            "NANOIF_LLM_PROFILE": "custom",
            "NANOIF_LLM_BASE_URL": "http://x/v1",
            "NANOIF_LLM_API_KEY": "k",
            "NANOIF_LLM_MODEL": "m",
        }
    )
    assert (s.base_url, s.api_key, s.model) == ("http://x/v1", "k", "m")


def test_unknown_profile_is_a_config_error():
    with pytest.raises(LLMConfigError, match="unknown NANOIF_LLM_PROFILE"):
        Settings.from_env({"NANOIF_LLM_PROFILE": "nope"})


def test_every_override_is_applied():
    s = Settings.from_env(
        {
            "NANOIF_LLM_BASE_URL": "http://gw/v1",
            "NANOIF_LLM_API_KEY": "sk",
            "NANOIF_LLM_MODEL": "deepseek-v4-flash",
            "NANOIF_LLM_TIMEOUT_S": "30.5",
            "NANOIF_LLM_MAX_RETRIES": "1",
            "NANOIF_LLM_MAX_CONCURRENCY": "2",
            "NANOIF_LLM_REASONING_EFFORT": "medium",
            "NANOIF_LLM_MAX_TOKENS_PER_JOB": "5000",
            "NANOIF_LLM_JSON_MODE": "object",
        }
    )
    assert s.profile == "exe"
    assert s.base_url == "http://gw/v1"
    assert s.api_key == "sk"
    assert s.model == "deepseek-v4-flash"
    assert s.timeout_s == 30.5
    assert s.max_retries == 1
    assert s.max_concurrency == 2
    assert s.reasoning_effort == "medium"
    assert s.max_tokens_per_job == 5000
    assert s.json_mode == "object"


@pytest.mark.parametrize(
    "key,value",
    [
        ("NANOIF_LLM_TIMEOUT_S", "soon"),
        ("NANOIF_LLM_MAX_RETRIES", "-1"),
        ("NANOIF_LLM_MAX_CONCURRENCY", "0"),
        ("NANOIF_LLM_MAX_TOKENS_PER_JOB", "2M"),
        ("NANOIF_LLM_REASONING_EFFORT", "extreme"),
        ("NANOIF_LLM_JSON_MODE", "yaml"),
    ],
)
def test_bad_values_are_config_errors(key, value):
    with pytest.raises(LLMConfigError):
        Settings.from_env({key: value})


def test_reasoning_model_detection():
    assert is_reasoning_model("gpt-oss-120b")
    assert is_reasoning_model("accounts/fireworks/models/gpt-oss-120b")
    assert is_reasoning_model("gpt-oss:20b")
    assert is_reasoning_model("fireworks/glm-5p3-flash")
    assert not is_reasoning_model("llama-3.1-70b-instruct")


def test_exe_default_model_is_a_gateway_id():
    # The exe.dev gateway lists models with a provider prefix, e.g. "fireworks/gpt-oss-120b".
    # Chosen by the eval (tests/eval/baselines/exe.json); see the eval-prompts skill.
    assert Settings.from_env({}).model == "fireworks/glm-5p3-flash"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 10.0), ("", 10.0), ("25", 25.0), ("2.5", 2.5), ("0", 0.0), ("off", None)],
)
def test_monthly_cap_parses(raw, expected):
    env = {} if raw is None else {"NANOIF_LLM_MONTHLY_USD": raw}
    assert Settings.from_env(env).monthly_usd == expected


@pytest.mark.parametrize("raw", ["-1", "ten", "OFF", "nan", "inf"])
def test_monthly_cap_rejects_anything_else(raw):
    with pytest.raises(LLMConfigError, match="NANOIF_LLM_MONTHLY_USD"):
        Settings.from_env({"NANOIF_LLM_MONTHLY_USD": raw})


def test_ledger_dir_is_explicit_only_when_set(tmp_path):
    assert Settings.from_env({}).ledger_dir is None
    assert Settings.from_env({"NANOIF_LLM_LEDGER_DIR": str(tmp_path)}).ledger_dir == tmp_path
