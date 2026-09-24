"""FakeLLM scripting, RecordingLLM fixtures, and ReplayLLM playback."""

import json

import pytest

from nanoif.llm.client import LLMResult, Usage
from nanoif.llm.errors import (
    LLMConfigError,
    LLMSchemaError,
    LLMTransportError,
    LLMTruncatedError,
)
from nanoif.llm.fake import FakeLLM, FakeLLMError, RecordingLLM, ReplayLLM

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def test_list_script_is_consumed_in_order_and_calls_are_recorded():
    fake = FakeLLM([{"answer": "one"}, '{"answer": "two"}', "free text"])
    r1 = fake.complete(system="s", user="u1", schema=SCHEMA, tag="a")
    r2 = fake.complete(system="s", user="u2", schema=SCHEMA, tag="b")
    r3 = fake.complete(system="s", user="u3")
    assert r1.data == {"answer": "one"}
    assert json.loads(r1.text) == {"answer": "one"}
    assert r2.data == {"answer": "two"}
    assert r3.text == "free text" and r3.data is None
    assert [c.tag for c in fake.calls] == ["a", "b", ""]
    assert fake.calls[0].user == "u1"
    assert fake.calls[0].schema == SCHEMA


def test_script_exhaustion_is_a_fake_error_not_a_default_result():
    fake = FakeLLM([{"answer": "x"}])
    fake.complete(system="s", user="u")
    with pytest.raises(FakeLLMError, match="exhausted"):
        fake.complete(system="s", user="u")


def test_tag_keyed_script():
    fake = FakeLLM({"extract": [{"answer": "e1"}, {"answer": "e2"}], "merge": {"answer": "m"}})
    assert fake.complete(system="s", user="u", tag="merge").data == {"answer": "m"}
    assert fake.complete(system="s", user="u", tag="extract").data == {"answer": "e1"}
    assert fake.complete(system="s", user="u", tag="extract").data == {"answer": "e2"}
    with pytest.raises(FakeLLMError, match="no scripted response for tag 'extract'"):
        fake.complete(system="s", user="u", tag="extract")
    with pytest.raises(FakeLLMError):
        fake.complete(system="s", user="u", tag="unknown")


def test_callable_script_sees_the_call():
    fake = FakeLLM(lambda call: {"answer": call.user.upper()})
    assert fake.complete(system="s", user="hi", schema=SCHEMA).data == {"answer": "HI"}


def test_scripted_failures_raise_typed_errors():
    fake = FakeLLM(
        [
            FakeLLM.transport_error("gateway down", status=503),
            FakeLLM.truncated(),
            FakeLLM.invalid_json(),
            {"wrong": "shape"},
        ]
    )
    with pytest.raises(LLMTransportError) as info:
        fake.complete(system="s", user="u")
    assert info.value.status == 503
    with pytest.raises(LLMTruncatedError):
        fake.complete(system="s", user="u")
    with pytest.raises(LLMSchemaError):
        fake.complete(system="s", user="u", schema=SCHEMA)
    with pytest.raises(LLMSchemaError, match="required"):
        fake.complete(system="s", user="u", schema=SCHEMA)
    assert len(fake.calls) == 4


def test_llm_result_script_item_is_returned_verbatim():
    result = LLMResult("t", {"answer": "x"}, Usage(1, 1, 0), "m", 5, 2, "stop")
    assert FakeLLM([result]).complete(system="s", user="u") is result


def test_usage_summary_counts_calls():
    fake = FakeLLM([{"answer": "a"}, {"answer": "b"}], usage=Usage(7, 3, 1))
    fake.complete(system="s", user="u")
    fake.complete(system="s", user="u")
    summary = fake.usage_summary()
    assert summary["calls"] == 2
    assert summary["prompt_tokens"] == 14
    assert summary["total_tokens"] == 20
    assert summary["reasoning_tokens"] == 2


def test_recording_then_replay_round_trips_results_and_errors(tmp_path):
    fixtures = tmp_path / "llm"
    inner = FakeLLM(
        [{"answer": "first"}, {"answer": "second"}, FakeLLM.transport_error("down")],
        usage=Usage(5, 2, 0),
    )
    recorder = RecordingLLM(inner, fixtures)
    recorder.complete(system="sys", user="u1", schema=SCHEMA, tag="extract:Day 1 EV")
    recorder.complete(system="sys", user="u2", schema=SCHEMA, tag="extract:Day 1 EV")
    with pytest.raises(LLMTransportError):
        recorder.complete(system="sys", user="u3", tag="merge")
    names = sorted(p.name for p in fixtures.glob("*.json"))
    assert names == ["extract_Day_1_EV-1.json", "extract_Day_1_EV-2.json", "merge-1.json"]
    record = json.loads((fixtures / "extract_Day_1_EV-1.json").read_text())
    assert record["request"]["user"] == "u1"
    assert record["request"]["schema"] == SCHEMA
    assert record["response"]["data"] == {"answer": "first"}
    assert record["response"]["usage"] == {
        "prompt_tokens": 5,
        "completion_tokens": 2,
        "reasoning_tokens": 0,
    }
    assert (
        json.loads((fixtures / "merge-1.json").read_text())["error"]["type"] == "LLMTransportError"
    )
    assert recorder.usage_summary()["calls"] == 3

    replay = ReplayLLM(fixtures)
    r1 = replay.complete(system="sys", user="u1", schema=SCHEMA, tag="extract:Day 1 EV")
    r2 = replay.complete(system="sys", user="u2", schema=SCHEMA, tag="extract:Day 1 EV")
    assert (r1.data, r2.data) == ({"answer": "first"}, {"answer": "second"})
    assert r1.usage == Usage(5, 2, 0)
    with pytest.raises(LLMTransportError, match="replayed: down"):
        replay.complete(system="sys", user="u3", tag="merge")
    with pytest.raises(FakeLLMError, match="no recording left"):
        replay.complete(system="sys", user="u4", tag="merge")
    assert replay.usage_summary()["prompt_tokens"] == 10
    assert len(replay.calls) == 4


def test_replay_rejects_missing_dir_and_corrupt_fixture(tmp_path):
    with pytest.raises(LLMConfigError, match="does not exist"):
        ReplayLLM(tmp_path / "nope")
    (tmp_path / "x-1.json").write_text("{corrupt", encoding="utf-8")
    with pytest.raises(LLMConfigError, match="not valid JSON"):
        ReplayLLM(tmp_path)
