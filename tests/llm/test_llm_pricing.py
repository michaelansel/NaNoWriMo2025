"""Price table lookups and USD estimates."""

import pytest

from nanoif.llm.client import Usage
from nanoif.llm.pricing import MODEL_RATES, estimate_usd, normalize_model, rate_for


def test_table_has_the_agreed_rates():
    assert MODEL_RATES["gpt-oss-120b"].input_per_m == 0.15
    assert MODEL_RATES["gpt-oss-120b"].output_per_m == 0.60
    assert MODEL_RATES["gpt-oss-20b"].input_per_m == 0.07
    assert MODEL_RATES["deepseek-v4-flash"].output_per_m == 0.28


@pytest.mark.parametrize(
    "model,key",
    [
        ("gpt-oss-120b", "gpt-oss-120b"),
        ("accounts/fireworks/models/gpt-oss-120b", "gpt-oss-120b"),
        ("GPT-OSS:20b", "gpt-oss-20b"),
        ("openai/gpt-oss-20b", "gpt-oss-20b"),
        ("gpt-oss-120b-fp8", "gpt-oss-120b"),
        # ids as the exe.dev gateway lists them at /v1/models
        ("fireworks/gpt-oss-120b", "gpt-oss-120b"),
        ("fireworks/deepseek-v4-flash-0731", "deepseek-v4-flash"),
    ],
)
def test_model_ids_normalize_to_table_keys(model, key):
    assert rate_for(model)[1] == key
    assert normalize_model(model).startswith(key)


def test_estimate_uses_input_and_output_rates():
    est = estimate_usd("gpt-oss-120b", Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000))
    assert est.usd == pytest.approx(0.75)
    assert est.known is True
    assert est.model_key == "gpt-oss-120b"


def test_exe_profile_reuses_the_model_rate():
    usage = Usage(prompt_tokens=200_000, completion_tokens=10_000)
    direct = estimate_usd("gpt-oss-120b", usage, profile="fireworks")
    via_exe = estimate_usd("gpt-oss-120b", usage, profile="exe")
    assert via_exe.usd == pytest.approx(direct.usd)
    assert via_exe.usd == pytest.approx(0.036)


@pytest.mark.intent("ADR-016")
def test_unknown_model_is_zero_and_flagged():
    est = estimate_usd("mystery-model", Usage(prompt_tokens=1000, completion_tokens=1000))
    assert est.usd == 0.0
    assert est.known is False
    assert est.model_key is None
