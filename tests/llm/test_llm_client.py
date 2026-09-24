"""LLMClient behavior with a fake transport; nothing here opens a socket."""

import json
import threading

import httpx2
import openai
import pytest

from nanoif.llm.client import (
    LLMClient,
    OpenAITransport,
    TransportRequest,
    TransportResponse,
    Usage,
)
from nanoif.llm.errors import (
    LLMBudgetExceeded,
    LLMSchemaError,
    LLMTransportError,
    LLMTruncatedError,
)
from nanoif.llm.profiles import Settings

SCHEMA = {
    "title": "Answer",
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


DEFAULT_USAGE = Usage(10, 5, 2)


def ok(text, usage=DEFAULT_USAGE, finish="stop", model="gpt-oss-120b"):
    return TransportResponse(text=text, finish_reason=finish, usage=usage, model=model)


class ScriptedTransport:
    """Returns or raises scripted items in order and records every request."""

    def __init__(self, items):
        self.items = list(items)
        self.requests: list[TransportRequest] = []

    def __call__(self, request):
        self.requests.append(request)
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def make(items, log=None, **overrides):
    overrides.setdefault("model", "gpt-oss-120b")
    settings = Settings(**overrides)
    transport = ScriptedTransport(items)
    lines: list[str] = []
    client = LLMClient(settings, transport=transport, log=log or lines.append)
    return client, transport, lines


def call_logs(lines):
    return [json.loads(line) for line in lines if "tag" in json.loads(line)]


def test_free_text_completion_returns_text_and_no_data():
    client, transport, lines = make([ok("hello")])
    result = client.complete(system="s", user="u", tag="t1")
    assert result.text == "hello"
    assert result.data is None
    assert result.attempts == 1
    assert result.finish_reason == "stop"
    assert result.usage == Usage(10, 5, 2)
    assert transport.requests[0].response_format is None
    assert transport.requests[0].messages == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ]


def test_schema_mode_sends_strict_json_schema_and_validates():
    client, transport, _ = make([ok('{"answer": "yes"}')])
    result = client.complete(system="s", user="u", schema=SCHEMA)
    assert result.data == {"answer": "yes"}
    fmt = transport.requests[0].response_format
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"] == SCHEMA
    assert fmt["json_schema"]["name"] == "Answer"
    assert "<output_schema>" not in transport.requests[0].messages[0]["content"]


def test_prompt_mode_embeds_schema_and_sends_no_response_format():
    client, transport, _ = make([ok('```json\n{"answer": "a"}\n```')], json_mode="prompt")
    result = client.complete(system="sys", user="u", schema=SCHEMA)
    assert result.data == {"answer": "a"}
    request = transport.requests[0]
    assert request.response_format is None
    assert request.messages[0]["content"].startswith("sys\n\n<output_schema>")
    assert '"answer"' in request.messages[0]["content"]


def test_truncation_raises_and_is_accounted():
    client, _, lines = make([ok('{"answer": "ye', finish="length")])
    with pytest.raises(LLMTruncatedError, match="finish_reason=length"):
        client.complete(system="s", user="u", schema=SCHEMA, tag="cut")
    summary = client.usage_summary()
    assert summary["calls"] == 1
    assert summary["prompt_tokens"] == 10
    log = call_logs(lines)[0]
    assert log["error"] == "LLMTruncatedError"
    assert log["tag"] == "cut"


def test_transport_error_propagates_untouched():
    client, _, _ = make([LLMTransportError("boom", status=503)])
    with pytest.raises(LLMTransportError, match="boom"):
        client.complete(system="s", user="u")


def test_400_on_response_format_falls_back_to_json_object_once():
    rejected = LLMTransportError(
        "provider returned HTTP 400: response_format json_schema unsupported", status=400
    )
    client, transport, lines = make([rejected, ok('{"answer": "b"}'), ok('{"answer": "c"}')])
    result = client.complete(system="sys", user="u", schema=SCHEMA)
    assert result.data == {"answer": "b"}
    assert result.attempts == 1
    first, second = transport.requests[:2]
    assert first.response_format["type"] == "json_schema"
    assert second.response_format == {"type": "json_object"}
    assert "<output_schema>" in second.messages[0]["content"]
    assert second.messages[1] == {"role": "user", "content": "u"}
    # The fallback sticks for the rest of the client's life.
    client.complete(system="sys", user="u2", schema=SCHEMA)
    assert transport.requests[2].response_format == {"type": "json_object"}
    assert len(transport.requests) == 3
    events = [json.loads(line).get("event") for line in lines]
    assert events.count("json_mode_fallback") == 1
    assert client.usage_summary()["json_mode"] == "object"


def test_400_unrelated_to_response_format_is_raised():
    client, _, _ = make([LLMTransportError("HTTP 400: model not found", status=400)])
    with pytest.raises(LLMTransportError, match="model not found"):
        client.complete(system="s", user="u", schema=SCHEMA)


def test_repair_round_appends_validation_error_and_previous_output():
    client, transport, _ = make(
        [ok("I think the answer is: {oops"), ok('{"answer": "fixed"}', usage=Usage(20, 8, 0))]
    )
    result = client.complete(system="s", user="u", schema=SCHEMA)
    assert result.data == {"answer": "fixed"}
    assert result.attempts == 2
    assert result.usage == Usage(30, 13, 2)
    repair = transport.requests[1].messages
    assert repair[:2] == transport.requests[0].messages
    assert repair[2] == {"role": "assistant", "content": "I think the answer is: {oops"}
    assert repair[3]["role"] == "user"
    assert "<previous_output>" in repair[3]["content"]
    assert "I think the answer is" in repair[3]["content"]
    assert "<validation_error>" in repair[3]["content"]


def test_schema_violation_triggers_repair_with_readable_error():
    client, transport, _ = make([ok('{"reply": 1}'), ok('{"answer": "ok"}')])
    client.complete(system="s", user="u", schema=SCHEMA)
    error_block = transport.requests[1].messages[3]["content"]
    assert "'answer' is a required property" in error_block


def test_schema_failure_after_repair_raises_schema_error():
    client, _, lines = make([ok("nope"), ok("still nope")])
    with pytest.raises(LLMSchemaError, match="after one repair round"):
        client.complete(system="s", user="u", schema=SCHEMA, tag="x")
    log = call_logs(lines)[0]
    assert log["attempts"] == 2
    assert log["error"] == "LLMSchemaError"
    assert client.usage_summary()["prompt_tokens"] == 20


def test_budget_is_checked_before_the_call_that_would_exceed_it():
    client, transport, _ = make(
        [ok("a", usage=Usage(900, 50, 0)), ok("b")], max_tokens_per_job=1000
    )
    client.complete(system="s", user="u")
    with pytest.raises(LLMBudgetExceeded) as info:
        client.complete(system="s" * 400, user="u")
    assert info.value.spent == 950
    assert info.value.budget == 1000
    assert len(transport.requests) == 1


def test_budget_blocks_an_oversized_first_prompt():
    client, transport, _ = make([ok("a")], max_tokens_per_job=50)
    with pytest.raises(LLMBudgetExceeded):
        client.complete(system="x" * 1000, user="u")
    assert transport.requests == []


def test_usage_summary_sums_calls_and_prices_them():
    client, _, _ = make([ok("a", usage=Usage(1000, 2000, 500)), ok("b", usage=Usage(500, 100, 0))])
    client.complete(system="s", user="u")
    client.complete(system="s", user="u")
    summary = client.usage_summary()
    assert summary["calls"] == 2
    assert summary["prompt_tokens"] == 1500
    assert summary["completion_tokens"] == 2100
    assert summary["reasoning_tokens"] == 500
    assert summary["total_tokens"] == 3600
    expected = (1000 * 0.15 + 2000 * 0.60 + 500 * 0.15 + 100 * 0.60) / 1e6
    assert summary["usd"] == pytest.approx(expected, abs=1e-9)
    assert summary["usd_known"] is True
    assert summary["budget_remaining"] == 2_000_000 - 3600
    assert summary["profile"] == "exe"


def test_unknown_model_flags_usd_unknown():
    client, _, _ = make([ok("a", model="mystery-7b")], model="mystery-7b")
    client.complete(system="s", user="u")
    summary = client.usage_summary()
    assert summary["usd"] == 0.0
    assert summary["usd_known"] is False


def test_log_line_has_required_keys_and_config_logged_once():
    client, _, lines = make([ok("a"), ok("b")])
    client.complete(system="s", user="u", tag="one")
    client.complete(system="s", user="u", tag="two")
    parsed = [json.loads(line) for line in lines]
    assert [p.get("event") for p in parsed].count("llm_config") == 1
    assert parsed[0]["event"] == "llm_config"
    calls = call_logs(lines)
    assert [c["tag"] for c in calls] == ["one", "two"]
    for key in (
        "tag",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "reasoning_tokens",
        "latency_ms",
        "attempts",
        "usd",
    ):
        assert key in calls[0]


def test_reasoning_model_bumps_max_tokens_and_passes_effort_via_api():
    client, transport, _ = make([ok("a")], reasoning_effort="low")
    client.complete(system="s", user="u", max_tokens=1000, reasoning_effort="high")
    request = transport.requests[0]
    assert request.max_tokens == 8000
    assert request.reasoning_effort == "high"
    assert "high" not in request.messages[0]["content"]
    assert "high" not in request.messages[1]["content"]


def test_settings_effort_is_the_default_and_plain_models_keep_max_tokens():
    client, transport, _ = make([ok("a")], model="llama-3.1-8b", reasoning_effort="medium")
    client.complete(system="s", user="u", max_tokens=1000)
    assert transport.requests[0].reasoning_effort == "medium"
    assert transport.requests[0].max_tokens == 8000
    client2, transport2, _ = make([ok("a")], model="llama-3.1-8b")
    client2.complete(system="s", user="u", max_tokens=1000)
    assert transport2.requests[0].reasoning_effort is None
    assert transport2.requests[0].max_tokens == 1000


def test_usage_accounting_is_thread_safe():
    n = 32
    client, _, _ = make([ok("a", usage=Usage(3, 2, 1)) for _ in range(n)], max_concurrency=8)
    lock = threading.Lock()

    def run():
        client.complete(system="s", user="u")

    threads = [threading.Thread(target=run) for _ in range(n)]
    with lock:
        for t in threads:
            t.start()
    for t in threads:
        t.join()
    summary = client.usage_summary()
    assert summary["calls"] == n
    assert summary["prompt_tokens"] == 3 * n
    assert summary["reasoning_tokens"] == n


# -- OpenAITransport against a stub SDK client -----------------------------------------


class _StubCompletions:
    def __init__(self, outcome):
        self.outcome = outcome
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class _StubSDK:
    def __init__(self, outcome):
        self.chat = type("Chat", (), {})()
        self.chat.completions = _StubCompletions(outcome)


def _completion(content='{"answer": "x"}', finish="stop", choices=True, usage=True):
    payload = {
        "id": "c1",
        "object": "chat.completion",
        "created": 1,
        "model": "served-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish,
                "message": {"role": "assistant", "content": content},
            }
        ]
        if choices
        else [],
    }
    if usage:
        payload["usage"] = {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
            "completion_tokens_details": {"reasoning_tokens": 4},
        }
    return openai.types.chat.ChatCompletion.model_validate(payload)


def _request(**overrides):
    base = dict(
        model="gpt-oss-120b",
        messages=[{"role": "user", "content": "u"}],
        max_tokens=100,
        temperature=0.0,
        response_format={"type": "json_object"},
        reasoning_effort="low",
    )
    base.update(overrides)
    return TransportRequest(**base)


def _http_error(cls, status, message):
    request = httpx2.Request("POST", "http://x/v1/chat/completions")
    response = httpx2.Response(status, request=request, json={"error": {"message": message}})
    return cls(message, response=response, body={"error": {"message": message}})


def test_openai_transport_maps_response_and_forwards_parameters():
    sdk = _StubSDK(_completion())
    transport = OpenAITransport(Settings(), client=sdk)
    response = transport(_request())
    assert response.text == '{"answer": "x"}'
    assert response.finish_reason == "stop"
    assert response.usage == Usage(11, 7, 4)
    assert response.model == "served-model"
    sent = sdk.chat.completions.kwargs
    assert sent["model"] == "gpt-oss-120b"
    assert sent["max_tokens"] == 100
    assert sent["temperature"] == 0.0
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["reasoning_effort"] == "low"


def test_openai_transport_omits_optional_parameters_when_absent():
    sdk = _StubSDK(_completion(usage=False))
    response = OpenAITransport(Settings(), client=sdk)(
        _request(response_format=None, reasoning_effort=None)
    )
    assert response.usage == Usage()
    sent = sdk.chat.completions.kwargs
    assert "response_format" not in sent
    assert "reasoning_effort" not in sent


def test_openai_transport_maps_status_errors_with_status_and_body():
    err = _http_error(openai.BadRequestError, 400, "response_format is not supported")
    transport = OpenAITransport(Settings(), client=_StubSDK(err))
    with pytest.raises(LLMTransportError) as info:
        transport(_request())
    assert info.value.status == 400
    assert "response_format" in str(info.value)
    assert info.value.body["error"]["message"] == "response_format is not supported"


def test_openai_transport_maps_connection_and_timeout_errors():
    request = httpx2.Request("POST", "http://x/v1/chat/completions")
    for err in (
        openai.APIConnectionError(request=request),
        openai.APITimeoutError(request=request),
    ):
        transport = OpenAITransport(Settings(), client=_StubSDK(err))
        with pytest.raises(LLMTransportError) as info:
            transport(_request())
        assert info.value.status is None


def test_openai_transport_rejects_empty_choices():
    transport = OpenAITransport(Settings(), client=_StubSDK(_completion(choices=False)))
    with pytest.raises(LLMTransportError, match="no choices"):
        transport(_request())


def test_openai_transport_builds_sdk_client_from_settings():
    settings = Settings(base_url="http://gw/v1", api_key="k", timeout_s=12.0, max_retries=2)
    transport = OpenAITransport(settings)
    sdk = transport._client
    assert str(sdk.base_url).startswith("http://gw/v1")
    assert sdk.api_key == "k"
    assert sdk.max_retries == 2
    assert sdk.timeout == 12.0
