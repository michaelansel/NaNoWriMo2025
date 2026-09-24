"""Test doubles for the LLM client: scripted, recording, and replaying completers.

``FakeLLM`` answers from a script so reviewers and extractors can be unit-tested with no
network. ``RecordingLLM`` wraps a real client and writes each exchange to a fixture
directory; ``ReplayLLM`` plays those fixtures back.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nanoif.llm.client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    Completer,
    LLMResult,
    Usage,
)
from nanoif.llm.errors import (
    LLMBudgetExceeded,
    LLMConfigError,
    LLMError,
    LLMSchemaError,
    LLMTransportError,
    LLMTruncatedError,
)
from nanoif.llm.schema import extract_json, validate

_ERROR_TYPES: dict[str, type[LLMError]] = {
    cls.__name__: cls
    for cls in (
        LLMError,
        LLMConfigError,
        LLMTransportError,
        LLMTruncatedError,
        LLMSchemaError,
        LLMBudgetExceeded,
    )
}


DEFAULT_FAKE_USAGE = Usage(prompt_tokens=100, completion_tokens=50, reasoning_tokens=0)


class FakeLLMError(LLMError):
    """The fake was driven past its script (a test bug, not a model failure)."""


@dataclass(frozen=True)
class FakeCall:
    """One recorded ``complete`` invocation."""

    system: str
    user: str
    schema: dict[str, Any] | None
    max_tokens: int
    temperature: float
    reasoning_effort: str | None
    tag: str


ScriptedResponse = Any
ResponseScript = (
    Sequence[ScriptedResponse]
    | Mapping[str, ScriptedResponse | Sequence[ScriptedResponse]]
    | Callable[[FakeCall], ScriptedResponse]
)


class FakeLLM:
    """A scripted completer with the same ``complete`` signature as ``LLMClient``.

    A scripted response can be a ``dict`` (returned as ``data`` after schema validation),
    a ``str`` (raw text, parsed when a schema is given), an ``LLMResult`` (returned as is),
    or an exception instance (raised). Use :meth:`transport_error`, :meth:`truncated`, and
    :meth:`invalid_json` to build failures readably.

    Args:
        responses: A list consumed in order, a mapping from ``tag`` to a response or list
            of responses, or a callable taking the :class:`FakeCall`.
        model: Model id reported in results and the summary.
        usage: Usage charged per call.
    """

    def __init__(
        self,
        responses: ResponseScript | None = None,
        *,
        model: str = "fake-model",
        usage: Usage = DEFAULT_FAKE_USAGE,
    ) -> None:
        self.model = model
        self.usage_per_call = usage
        self.calls: list[FakeCall] = []
        self._lock = threading.Lock()
        self._total = Usage()
        self._script = responses if responses is not None else []
        self._queue: list[ScriptedResponse] = []
        self._by_tag: dict[str, list[ScriptedResponse]] = {}
        if callable(self._script):
            pass
        elif isinstance(self._script, Mapping):
            for tag, value in self._script.items():
                items = list(value) if isinstance(value, (list, tuple)) else [value]
                self._by_tag[tag] = items
        else:
            self._queue = list(self._script)

    @staticmethod
    def transport_error(message: str = "connection refused", status: int | None = None) -> LLMError:
        """Build a scripted transport failure."""
        return LLMTransportError(message, status=status)

    @staticmethod
    def truncated(text: str = '{"partial": tr') -> LLMError:
        """Build a scripted truncation (``finish_reason == "length"``)."""
        return LLMTruncatedError("model stopped at max_tokens (finish_reason=length)", text=text)

    @staticmethod
    def invalid_json(text: str = "Sure! Here is the answer: not json at all") -> str:
        """Return text that fails JSON extraction so ``complete`` raises ``LLMSchemaError``."""
        return text

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        reasoning_effort: str | None = None,
        tag: str = "",
    ) -> LLMResult:
        """Answer from the script, recording the call.

        Raises:
            FakeLLMError: No scripted response is left for this call.
            LLMError: The scripted response was an exception, or text that fails the schema.
        """
        call = FakeCall(system, user, schema, max_tokens, temperature, reasoning_effort, tag)
        with self._lock:
            self.calls.append(call)
            scripted = self._next(call)
            self._total = self._total + self.usage_per_call
        if isinstance(scripted, BaseException):
            raise scripted
        if isinstance(scripted, LLMResult):
            return scripted
        if isinstance(scripted, str):
            text = scripted
            data = None
            if schema is not None:
                data = extract_json(text)
                validate(data, schema)
        else:
            data = scripted
            text = json.dumps(scripted)
            if schema is not None:
                validate(data, schema)
        return LLMResult(
            text=text,
            data=data,
            usage=self.usage_per_call,
            model=self.model,
            latency_ms=0,
            attempts=1,
            finish_reason="stop",
        )

    def usage_summary(self) -> dict[str, Any]:
        """Return totals in the same shape as ``LLMClient.usage_summary``."""
        with self._lock:
            total = self._total
            calls = len(self.calls)
        return {
            "profile": "fake",
            "model": self.model,
            "json_mode": "schema",
            "calls": calls,
            "prompt_tokens": total.prompt_tokens,
            "completion_tokens": total.completion_tokens,
            "reasoning_tokens": total.reasoning_tokens,
            "total_tokens": total.total_tokens,
            "usd": 0.0,
            "usd_known": False,
            "budget_tokens": 0,
            "budget_remaining": 0,
        }

    def _next(self, call: FakeCall) -> ScriptedResponse:
        if callable(self._script):
            return self._script(call)
        if self._by_tag:
            items = self._by_tag.get(call.tag)
            if not items:
                raise FakeLLMError(f"FakeLLM has no scripted response for tag {call.tag!r}")
            return items.pop(0)
        if not self._queue:
            raise FakeLLMError(f"FakeLLM script exhausted after {len(self.calls) - 1} calls")
        return self._queue.pop(0)


def _fixture_name(tag: str, n: int) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", tag).strip("_") or "untagged"
    return f"{safe}-{n}.json"


@dataclass
class RecordingLLM:
    """Wrap a real completer and write each exchange to ``directory``.

    Files are named ``<tag>-<n>.json`` with ``n`` counting per tag from 1. Errors are
    recorded too (as ``{"error": {...}}``) and re-raised.

    Args:
        inner: The completer to wrap.
        directory: Where fixtures are written; created on first use.
    """

    inner: Completer
    directory: Path
    _counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        reasoning_effort: str | None = None,
        tag: str = "",
    ) -> LLMResult:
        """Delegate to ``inner`` and record the exchange."""
        self._counts[tag] += 1
        record: dict[str, Any] = {
            "tag": tag,
            "n": self._counts[tag],
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request": {
                "system": system,
                "user": user,
                "schema": schema,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "reasoning_effort": reasoning_effort,
            },
        }
        try:
            result = self.inner.complete(
                system=system,
                user=user,
                schema=schema,
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
                tag=tag,
            )
        except LLMError as exc:
            record["error"] = {"type": type(exc).__name__, "message": str(exc)}
            self._write(tag, record)
            raise
        record["response"] = asdict(result)
        self._write(tag, record)
        return result

    def usage_summary(self) -> dict[str, Any]:
        """Return the wrapped completer's usage."""
        return self.inner.usage_summary()

    def _write(self, tag: str, record: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / _fixture_name(tag, record["n"])
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ReplayLLM:
    """Play back fixtures written by :class:`RecordingLLM`, in order per tag.

    Args:
        directory: Fixture directory.

    Raises:
        LLMConfigError: The directory is missing or a fixture is not valid JSON.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.calls: list[FakeCall] = []
        self._total = Usage()
        self._lock = threading.Lock()
        self._by_tag: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if not directory.is_dir():
            raise LLMConfigError(f"replay directory {directory} does not exist")
        for path in sorted(directory.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise LLMConfigError(f"fixture {path} is not valid JSON: {exc}") from exc
            if not isinstance(record, dict) or "tag" not in record or "n" not in record:
                raise LLMConfigError(f"fixture {path} lacks 'tag' and 'n'")
            self._by_tag[record["tag"]].append(record)
        for records in self._by_tag.values():
            records.sort(key=lambda r: int(r["n"]))

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        reasoning_effort: str | None = None,
        tag: str = "",
    ) -> LLMResult:
        """Return the next recorded result for ``tag`` or re-raise its recorded error.

        Raises:
            FakeLLMError: No recording is left for this tag.
            LLMError: The recording captured an error of this type.
        """
        with self._lock:
            self.calls.append(
                FakeCall(system, user, schema, max_tokens, temperature, reasoning_effort, tag)
            )
            records = self._by_tag.get(tag)
            if not records:
                raise FakeLLMError(f"no recording left for tag {tag!r} in {self.directory}")
            record = records.pop(0)
        if "error" in record:
            error = record["error"]
            cls = _ERROR_TYPES.get(error.get("type", ""), LLMError)
            raise cls(f"replayed: {error.get('message', '')}")
        response = record["response"]
        usage = Usage(**response["usage"])
        with self._lock:
            self._total = self._total + usage
        return LLMResult(
            text=response["text"],
            data=response["data"],
            usage=usage,
            model=response["model"],
            latency_ms=int(response.get("latency_ms", 0)),
            attempts=int(response.get("attempts", 1)),
            finish_reason=response.get("finish_reason"),
        )

    def usage_summary(self) -> dict[str, Any]:
        """Return totals over the replayed results."""
        with self._lock:
            total = self._total
            calls = len(self.calls)
        return {
            "profile": "replay",
            "model": "replay",
            "json_mode": "schema",
            "calls": calls,
            "prompt_tokens": total.prompt_tokens,
            "completion_tokens": total.completion_tokens,
            "reasoning_tokens": total.reasoning_tokens,
            "total_tokens": total.total_tokens,
            "usd": 0.0,
            "usd_known": False,
            "budget_tokens": 0,
            "budget_remaining": 0,
        }
