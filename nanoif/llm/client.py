"""OpenAI-compatible chat client with structured output, budget, and usage accounting.

The client talks to any OpenAI-compatible endpoint through the ``openai`` SDK (3.x). The
network boundary is the ``Transport`` callable so tests inject a fake transport and never
open a socket. Every failure raises a typed :class:`~nanoif.llm.errors.LLMError`;
nothing here returns a default-shaped success.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

import openai
from jinja2 import Environment, PackageLoader, StrictUndefined

from nanoif.llm.errors import (
    LLMBudgetExceeded,
    LLMConfigError,
    LLMError,
    LLMSchemaError,
    LLMTransportError,
    LLMTruncatedError,
)
from nanoif.llm.pricing import estimate_usd
from nanoif.llm.profiles import REASONING_MIN_MAX_TOKENS, Settings, is_reasoning_model
from nanoif.llm.schema import extract_json, validate

__all__ = [
    "LLMBudgetExceeded",
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMResult",
    "LLMSchemaError",
    "LLMTransportError",
    "LLMTruncatedError",
    "Completer",
    "OpenAITransport",
    "Transport",
    "TransportRequest",
    "TransportResponse",
    "Usage",
]

DEFAULT_MAX_TOKENS = 16000
DEFAULT_TEMPERATURE = 0.2
_REPAIR_TEMPLATE = Environment(
    loader=PackageLoader("nanoif.llm", "templates"),
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=False,
).get_template("repair.md")

LOG_KEYS = (
    "tag",
    "model",
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "latency_ms",
    "attempts",
    "usd",
)


@dataclass(frozen=True)
class Usage:
    """Token counts for one call or an accumulated total."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Prompt plus completion tokens (reasoning tokens are part of completion)."""
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
            self.reasoning_tokens + other.reasoning_tokens,
        )


@dataclass(frozen=True)
class LLMResult:
    """A successful completion.

    Attributes:
        text: Raw assistant text of the final attempt.
        data: Parsed and validated JSON when a schema was given, else ``None``.
        usage: Tokens spent across every attempt of this call.
        model: Model id the provider reported.
        latency_ms: Wall time for the whole call including the repair round.
        attempts: Number of transport round trips (1, or 2 after a repair or fallback).
        finish_reason: Provider finish reason of the final attempt.
    """

    text: str
    data: Any
    usage: Usage
    model: str
    latency_ms: int
    attempts: int
    finish_reason: str | None


@dataclass(frozen=True)
class TransportRequest:
    """Everything a transport needs to issue one chat completion."""

    model: str
    messages: list[dict[str, str]]
    max_tokens: int
    temperature: float
    response_format: dict[str, Any] | None
    reasoning_effort: str | None


@dataclass(frozen=True)
class TransportResponse:
    """What a transport returns for one chat completion."""

    text: str
    finish_reason: str | None
    usage: Usage
    model: str


Transport = Callable[[TransportRequest], TransportResponse]


class Completer(Protocol):
    """The interface reviewers and extractors program against."""

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
        """Run one completion; see :meth:`LLMClient.complete`."""
        ...

    def usage_summary(self) -> dict[str, Any]:
        """Return accumulated usage; see :meth:`LLMClient.usage_summary`."""
        ...


class OpenAITransport:
    """Transport backed by ``openai.OpenAI().chat.completions.create``.

    Args:
        settings: Connection settings (base URL, key, timeout, SDK retries).
        client: An already-built SDK client, injected by tests.
    """

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._client = client or openai.OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=settings.timeout_s,
            max_retries=settings.max_retries,
        )

    def __call__(self, request: TransportRequest) -> TransportResponse:
        """Send the request and normalize the SDK response or error.

        Args:
            request: The completion to run.

        Returns:
            The provider's first choice with its usage.

        Raises:
            LLMTransportError: Any SDK error, or a response with no choices.
        """
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.response_format is not None:
            kwargs["response_format"] = request.response_format
        if request.reasoning_effort is not None:
            kwargs["reasoning_effort"] = request.reasoning_effort
        try:
            completion = self._client.chat.completions.create(**kwargs)
        except openai.APIStatusError as exc:
            raise LLMTransportError(
                f"provider returned HTTP {exc.status_code}: {exc.message}",
                status=exc.status_code,
                body=exc.body,
            ) from exc
        except openai.APIConnectionError as exc:
            raise LLMTransportError(f"connection failed: {exc}") from exc
        except openai.OpenAIError as exc:
            raise LLMTransportError(f"SDK error: {exc}") from exc
        if not completion.choices:
            raise LLMTransportError("provider returned no choices", body=_dump(completion))
        choice = completion.choices[0]
        usage = Usage()
        if completion.usage is not None:
            details = completion.usage.completion_tokens_details
            reasoning = details.reasoning_tokens if details is not None else None
            usage = Usage(
                prompt_tokens=completion.usage.prompt_tokens or 0,
                completion_tokens=completion.usage.completion_tokens or 0,
                reasoning_tokens=reasoning or 0,
            )
        return TransportResponse(
            text=choice.message.content or "",
            finish_reason=choice.finish_reason,
            usage=usage,
            model=completion.model or request.model,
        )


def _dump(obj: Any) -> Any:
    dumper = getattr(obj, "model_dump", None)
    return dumper() if callable(dumper) else repr(obj)


@dataclass
class _Totals:
    calls: int = 0
    usage: Usage = field(default_factory=Usage)
    usd: float = 0.0
    usd_known: bool = True


class LLMClient:
    """Structured-output chat client with one repair round and a hard token budget.

    Args:
        settings: Effective settings, normally ``Settings.from_env()``.
        transport: Callable that performs the network call; defaults to
            :class:`OpenAITransport`. Tests pass a fake here.
        log: Sink for the per-call JSON log line; defaults to one line on stderr.
    """

    def __init__(
        self,
        settings: Settings,
        transport: Transport | None = None,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self.settings = settings
        self._transport: Transport = transport or OpenAITransport(settings)
        self._log = log or _stderr_line
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(settings.max_concurrency)
        self._totals = _Totals()
        self._json_mode = settings.json_mode
        self._logged_config = False

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
        """Run one chat completion, optionally constrained to a JSON schema.

        Args:
            system: System message. When a schema is used in ``object`` or ``prompt`` mode
                the schema is appended inside ``<output_schema>`` delimiters.
            user: User message; passage text is data and goes here.
            schema: JSON Schema the output must satisfy, or ``None`` for free text.
            max_tokens: Completion cap; raised to 8000 for reasoning models.
            temperature: Sampling temperature.
            reasoning_effort: Overrides the settings default for this call.
            tag: Short label for the log line and fixtures (for example ``extract:Day 1 EV``).

        Returns:
            The validated result.

        Raises:
            LLMBudgetExceeded: The call would push the job past its token budget.
            LLMTransportError: The provider could not be reached or answered with an error.
            LLMTruncatedError: The model hit ``max_tokens``.
            LLMSchemaError: Output was not valid JSON for the schema after one repair round.
        """
        effort = reasoning_effort
        if effort is None:
            effort = self.settings.reasoning_effort
        model = self.settings.model
        if (effort or is_reasoning_model(model)) and max_tokens < REASONING_MIN_MAX_TOKENS:
            max_tokens = REASONING_MIN_MAX_TOKENS
        self._log_config_once()

        started = time.perf_counter()
        attempts = 0
        spent = Usage()
        error: LLMError | None = None
        text = ""
        finish_reason: str | None = None
        reported_model = model
        data: Any = None
        try:
            messages = self._build_messages(system, user, schema)
            response, messages = self._send(messages, schema, max_tokens, temperature, effort)
            attempts += 1
            spent = spent + response.usage
            text, finish_reason = response.text, response.finish_reason
            reported_model = response.model
            self._raise_if_truncated(response, max_tokens)
            if schema is None:
                return _result(text, None, spent, reported_model, started, attempts, finish_reason)
            try:
                data = _parse(text, schema)
            except LLMSchemaError as first:
                repair = messages + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": _repair_message(text, first)},
                ]
                response, _ = self._send(repair, schema, max_tokens, temperature, effort)
                attempts += 1
                spent = spent + response.usage
                text, finish_reason = response.text, response.finish_reason
                reported_model = response.model
                self._raise_if_truncated(response, max_tokens)
                try:
                    data = _parse(text, schema)
                except LLMSchemaError as second:
                    raise LLMSchemaError(
                        f"output still invalid after one repair round: {second}",
                        text=text,
                        errors=second.errors,
                    ) from second
            return _result(text, data, spent, reported_model, started, attempts, finish_reason)
        except LLMError as exc:
            error = exc
            raise
        finally:
            self._record(spent, reported_model)
            self._emit_call_log(tag, reported_model, spent, started, attempts, error)

    def usage_summary(self) -> dict[str, Any]:
        """Return accumulated usage for comment headers and step summaries.

        Returns:
            Keys ``profile``, ``model``, ``json_mode``, ``calls``, ``prompt_tokens``,
            ``completion_tokens``, ``reasoning_tokens``, ``total_tokens``, ``usd``,
            ``usd_known``, ``budget_tokens``, ``budget_remaining``.
        """
        with self._lock:
            totals = self._totals
            usage = totals.usage
            return {
                "profile": self.settings.profile,
                "model": self.settings.model,
                "json_mode": self._json_mode,
                "calls": totals.calls,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "reasoning_tokens": usage.reasoning_tokens,
                "total_tokens": usage.total_tokens,
                "usd": round(totals.usd, 6),
                "usd_known": totals.usd_known,
                "budget_tokens": self.settings.max_tokens_per_job,
                "budget_remaining": max(self.settings.max_tokens_per_job - usage.total_tokens, 0),
            }

    # -- internals -----------------------------------------------------------------

    def _build_messages(
        self, system: str, user: str, schema: dict[str, Any] | None
    ) -> list[dict[str, str]]:
        if schema is not None and self._json_mode != "schema":
            block = json.dumps(schema, indent=1)
            system = f"{system}\n\n<output_schema>\n{block}\n</output_schema>"
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _response_format(self, schema: dict[str, Any] | None) -> dict[str, Any] | None:
        if schema is None or self._json_mode == "prompt":
            return None
        if self._json_mode == "object":
            return {"type": "json_object"}
        name = str(schema.get("title") or "output").replace(" ", "_")[:64]
        spec = {"name": name, "schema": schema, "strict": True}
        return {"type": "json_schema", "json_schema": spec}

    def _send(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
        effort: str | None,
    ) -> tuple[TransportResponse, list[dict[str, str]]]:
        """Send once, falling back from ``json_schema`` to ``json_object`` on a 400.

        Returns:
            The response and the messages actually sent (they change on fallback).
        """
        self._check_budget(messages, max_tokens)
        request = TransportRequest(
            model=self.settings.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=self._response_format(schema),
            reasoning_effort=effort,
        )
        try:
            with self._slots:
                return self._transport(request), messages
        except LLMTransportError as exc:
            if not (schema is not None and self._json_mode == "schema" and _rejects_format(exc)):
                raise
            self._json_mode = "object"
            self._emit(
                {
                    "event": "json_mode_fallback",
                    "from": "schema",
                    "to": "object",
                    "status": exc.status,
                    "reason": str(exc)[:200],
                }
            )
        # Rebuild with the schema embedded in the system prompt and retry once.
        system = messages[0]["content"]
        rebuilt = [
            {"role": "system", "content": self._build_messages(system, "", schema)[0]["content"]},
            *messages[1:],
        ]
        self._check_budget(rebuilt, max_tokens)
        request = TransportRequest(
            model=self.settings.model,
            messages=rebuilt,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=self._response_format(schema),
            reasoning_effort=effort,
        )
        with self._slots:
            return self._transport(request), rebuilt

    def _check_budget(self, messages: list[dict[str, str]], max_tokens: int) -> None:
        projected_prompt = sum(_estimate_tokens(m["content"]) for m in messages)
        budget = self.settings.max_tokens_per_job
        with self._lock:
            spent = self._totals.usage.total_tokens
        projected = spent + projected_prompt
        if spent >= budget or projected > budget:
            raise LLMBudgetExceeded(
                f"token budget {budget} would be exceeded: {spent} spent, "
                f"about {projected_prompt} more in the next prompt",
                spent=spent,
                budget=budget,
                projected=projected,
            )

    @staticmethod
    def _raise_if_truncated(response: TransportResponse, max_tokens: int) -> None:
        if response.finish_reason == "length":
            raise LLMTruncatedError(
                f"model stopped at max_tokens={max_tokens} (finish_reason=length)",
                text=response.text,
                max_tokens=max_tokens,
            )

    def _record(self, usage: Usage, model: str) -> None:
        estimate = estimate_usd(model, usage, self.settings.profile)
        with self._lock:
            self._totals.calls += 1
            self._totals.usage = self._totals.usage + usage
            self._totals.usd += estimate.usd
            if not estimate.known and usage.total_tokens:
                self._totals.usd_known = False

    def _emit_call_log(
        self,
        tag: str,
        model: str,
        usage: Usage,
        started: float,
        attempts: int,
        error: LLMError | None,
    ) -> None:
        line: dict[str, Any] = {
            "tag": tag,
            "model": model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "reasoning_tokens": usage.reasoning_tokens,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "attempts": attempts,
            "usd": round(estimate_usd(model, usage, self.settings.profile).usd, 6),
        }
        if error is not None:
            line["error"] = type(error).__name__
        self._emit(line)

    def _log_config_once(self) -> None:
        with self._lock:
            if self._logged_config:
                return
            self._logged_config = True
        s = self.settings
        self._emit(
            {
                "event": "llm_config",
                "profile": s.profile,
                "model": s.model,
                "base_url": s.base_url,
                "json_mode": self._json_mode,
                "reasoning_effort": s.reasoning_effort,
                "timeout_s": s.timeout_s,
                "max_retries": s.max_retries,
                "max_concurrency": s.max_concurrency,
                "budget_tokens": s.max_tokens_per_job,
            }
        )

    def _emit(self, payload: dict[str, Any]) -> None:
        self._log(json.dumps(payload, sort_keys=True))


def _stderr_line(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def _estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1


def _rejects_format(exc: LLMTransportError) -> bool:
    if exc.status != 400:
        return False
    haystack = f"{exc} {json.dumps(exc.body, default=str) if exc.body is not None else ''}".lower()
    return "response_format" in haystack or "json_schema" in haystack


def _parse(text: str, schema: dict[str, Any]) -> Any:
    data = extract_json(text)
    validate(data, schema)
    return data


def _repair_message(previous: str, error: LLMSchemaError) -> str:
    errors = list(error.errors) if error.errors else [str(error)]
    return _REPAIR_TEMPLATE.render(previous=previous, errors=errors).strip()


def _result(
    text: str,
    data: Any,
    usage: Usage,
    model: str,
    started: float,
    attempts: int,
    finish_reason: str | None,
) -> LLMResult:
    return LLMResult(
        text=text,
        data=data,
        usage=usage,
        model=model,
        latency_ms=int((time.perf_counter() - started) * 1000),
        attempts=attempts,
        finish_reason=finish_reason,
    )


def result_to_dict(result: LLMResult) -> dict[str, Any]:
    """Serialize a result for fixtures and reports.

    Args:
        result: The result to serialize.

    Returns:
        A JSON-ready dict with ``usage`` expanded.
    """
    return asdict(result)
