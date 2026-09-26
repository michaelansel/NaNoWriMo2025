"""The monthly spend cap in ``LLMClient``: refuse before sending, charge every response."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime

import pytest

from nanoif.llm.client import LLMClient, TransportResponse, Usage
from nanoif.llm.errors import (
    LLMBudgetExceeded,
    LLMLedgerError,
    LLMRunHalted,
    LLMSpendCapReached,
    LLMTransportError,
)
from nanoif.llm.ledger import SpendLedger
from nanoif.llm.pricing import UNPRICED_CAP_RATE
from nanoif.llm.profiles import Settings

SEPT = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
CAP_REASON = "monthly AI spend cap reached: $9.99 of $10.00 in 2026-09 (resets 2026-10-01 UTC)"


class Transport:
    """Returns scripted items; optionally blocks each call until released."""

    def __init__(self, items=None, gate: threading.Event | None = None):
        self.items = list(items or [])
        self.requests = []
        self.gate = gate
        self.arrived = threading.Semaphore(0)

    def __call__(self, request):
        self.requests.append(request)
        self.arrived.release()
        if self.gate is not None:
            assert self.gate.wait(10)
        item = self.items.pop(0) if self.items else ok()
        if isinstance(item, BaseException):
            raise item
        return item


USAGE = Usage(1000, 100, 0)


def ok(usage=USAGE, model="accounts/fireworks/models/gpt-oss-120b"):
    return TransportResponse(text="hi", finish_reason="stop", usage=usage, model=model)


def seed(directory, usd: float) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": "2026-09-02T00:00:00Z", "month": "2026-09", "profile": "exe",
        "model": "fireworks/gpt-oss-120b", "prompt_tokens": 1, "completion_tokens": 1,
        "usd": usd, "usd_known": True, "estimated": False, "tag": "seed", "run": None,
    }
    with (directory / "2026-09.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def lines(directory) -> list[dict]:
    path = directory / "2026-09.jsonl"
    if not path.exists():
        return []
    return [json.loads(raw) for raw in path.read_text().splitlines()]


def make(tmp_path, items=None, *, cap=10.0, model="fireworks/gpt-oss-120b", gate=None, **kw):
    settings = Settings(model=model, monthly_usd=cap, **kw)
    transport = Transport(items, gate)
    ledger = SpendLedger(tmp_path, explicit=True, clock=lambda: SEPT)
    client = LLMClient(settings, transport=transport, log=lambda _line: None, ledger=ledger)
    return client, transport


def test_halting_errors_share_a_base_with_a_reason():
    budget = LLMBudgetExceeded("over", spent=1, budget=1, projected=2)
    assert isinstance(budget, LLMRunHalted) and budget.reason == "token budget exhausted"
    capped = LLMSpendCapReached("capped", reason=CAP_REASON, month_usd=9.99, cap_usd=10.0)
    assert isinstance(capped, LLMRunHalted) and not isinstance(capped, LLMBudgetExceeded)
    assert isinstance(LLMLedgerError("bad", reason="ledger x"), LLMRunHalted)


@pytest.mark.intent("AC-continuity-review-32")
def test_call_that_would_pass_the_cap_is_refused_before_it_is_sent(tmp_path):
    seed(tmp_path, 9.995)
    client, transport = make(tmp_path)
    with pytest.raises(LLMSpendCapReached) as caught:
        client.complete(system="s", user="u", tag="t")
    assert caught.value.reason == CAP_REASON
    assert transport.requests == []
    assert len(lines(tmp_path)) == 1, "a refused call is not charged"


@pytest.mark.intent("AC-continuity-review-31")
def test_check_spend_refuses_when_the_cap_is_already_reached(tmp_path):
    seed(tmp_path, 10.0)
    client, _ = make(tmp_path)
    with pytest.raises(LLMSpendCapReached, match=r"\$10\.00 of \$10\.00 in 2026-09"):
        client.check_spend()


def test_check_spend_refuses_an_estimate_larger_than_what_is_left(tmp_path):
    seed(tmp_path, 7.0)
    client, _ = make(tmp_path)
    client.check_spend(2.5)
    with pytest.raises(LLMSpendCapReached):
        client.check_spend(3.5)


def test_zero_cap_blocks_all_paid_inference(tmp_path):
    client, transport = make(tmp_path, cap=0.0)
    with pytest.raises(LLMSpendCapReached):
        client.check_spend()
    with pytest.raises(LLMSpendCapReached):
        client.complete(system="s", user="u")
    assert transport.requests == []


def test_cap_off_never_refuses_but_still_records(tmp_path):
    seed(tmp_path, 500.0)
    client, transport = make(tmp_path, cap=None)
    client.check_spend(100.0)
    client.complete(system="s", user="u", tag="t")
    assert len(transport.requests) == 1
    summary = client.usage_summary()
    assert summary["month_cap_usd"] is None and summary["month_cap_reached"] is False
    assert len(lines(tmp_path)) == 2


def test_every_response_is_charged_to_the_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "4242")
    client, _ = make(tmp_path, [ok(), ok(Usage(2000, 50, 0))])
    client.complete(system="s", user="u", tag="first")
    client.complete(system="s", user="u", tag="second")
    first, second = lines(tmp_path)
    assert (first["tag"], first["prompt_tokens"], first["completion_tokens"]) == ("first", 1000, 100)
    assert first["usd"] == pytest.approx((1000 * 0.15 + 100 * 0.60) / 1e6)
    assert first["usd_known"] is True and first["estimated"] is False
    assert first["run"] == "4242" and first["month"] == "2026-09"
    assert second["prompt_tokens"] == 2000
    summary = client.usage_summary()
    assert summary["month"] == "2026-09"
    assert summary["month_usd"] == pytest.approx(first["usd"] + second["usd"], abs=1e-6)
    assert summary["month_cap_usd"] == 10.0 and summary["month_cap_reached"] is False


def test_unpriced_model_is_charged_at_the_fallback_rate(tmp_path):
    client, _ = make(tmp_path, [ok(model="mystery-model")], model="mystery-model")
    client.complete(system="s", user="u")
    (entry,) = lines(tmp_path)
    expected = (1000 * UNPRICED_CAP_RATE.input_per_m + 100 * UNPRICED_CAP_RATE.output_per_m) / 1e6
    assert entry["usd"] == pytest.approx(expected) and entry["usd_known"] is False
    assert client.usage_summary()["month_usd_known"] is False


def test_server_error_is_charged_its_pessimistic_estimate(tmp_path):
    client, _ = make(tmp_path, [LLMTransportError("boom", status=502)], max_retries=0)
    with pytest.raises(LLMTransportError):
        client.complete(system="s", user="u", tag="t", max_tokens=1000)
    (entry,) = lines(tmp_path)
    assert entry["estimated"] is True and entry["usd"] > 0


def test_client_error_is_not_charged(tmp_path):
    client, _ = make(tmp_path, [LLMTransportError("bad request", status=404)])
    with pytest.raises(LLMTransportError):
        client.complete(system="s", user="u")
    assert lines(tmp_path) == []


def test_concurrent_calls_cannot_jointly_pass_the_cap(tmp_path):
    # Each call reserves prompt + 8000 completion tokens (a reasoning model's floor):
    # about $0.0048. A $0.011 cap fits two in flight, not three.
    gate = threading.Event()
    client, transport = make(tmp_path, cap=0.011, gate=gate)
    errors: list[BaseException] = []

    def call():
        try:
            client.complete(system="s", user="u", max_tokens=8000)
        except BaseException as exc:  # noqa: BLE001 - collected for the assertion
            errors.append(exc)

    threads = [threading.Thread(target=call) for _ in range(2)]
    for thread in threads:
        thread.start()
    for _ in range(2):
        assert transport.arrived.acquire(timeout=5)
    for _ in range(2):
        with pytest.raises(LLMSpendCapReached):
            client.complete(system="s", user="u", max_tokens=8000)
    gate.set()
    for thread in threads:
        thread.join(5)
    assert errors == [] and len(transport.requests) == 2


def test_failed_append_keeps_the_result_and_halts_the_next_call(tmp_path, monkeypatch):
    client, transport = make(tmp_path, [ok(), ok()])

    def broken(**_entry):
        raise LLMLedgerError("disk full", reason="spend ledger could not be written: disk full")

    monkeypatch.setattr(client._ledger, "append", broken)
    assert client.complete(system="s", user="u").text == "hi"
    with pytest.raises(LLMLedgerError):
        client.complete(system="s", user="u")
    assert len(transport.requests) == 1


@pytest.mark.intent("AC-continuity-review-33")
def test_unreadable_ledger_refuses_every_call(tmp_path):
    tmp_path.joinpath("2026-09.jsonl").write_text("garbage\n", encoding="utf-8")
    client, transport = make(tmp_path)
    with pytest.raises(LLMLedgerError):
        client.check_spend()
    with pytest.raises(LLMLedgerError):
        client.complete(system="s", user="u")
    assert transport.requests == []
