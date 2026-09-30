"""The cost estimate of a review, and the monthly-cap refusal it drives for mode ``all``."""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from review_helpers import FIXTURES, answer

from nanoif.eval.run import prepare_eval_repo
from nanoif.llm.client import LLMClient, TransportResponse, Usage, prompt_token_bound
from nanoif.llm.errors import LLMSpendCapReached
from nanoif.llm.fake import FakeLLM
from nanoif.llm.ledger import SpendLedger
from nanoif.llm.pricing import MODEL_RATES, UNPRICED_CAP_RATE, cap_usd
from nanoif.llm.profiles import REASONING_MIN_MAX_TOKENS, Settings
from nanoif.review.runner import estimate_review, preflight, review
from nanoif.schemas.artifacts import validate_artifact

ENV = {"NANOIF_RUNNER": "local"}
SEPT = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
PRICED = "gpt-oss-120b"
TOLL = "The toll"


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("estimate") / "story"
    prepare_eval_repo(FIXTURES / "eval-story", root)
    return root


@pytest.fixture
def repo(built, tmp_path) -> Path:
    target = tmp_path / "story"
    shutil.copytree(built, target)
    return target


class SpendRecordingFake(FakeLLM):
    """Records every ``check_spend`` estimate; refuses with ``error`` when one is given."""

    def __init__(self, *args, error: LLMSpendCapReached | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.error = error
        self.checked: list[float] = []

    def check_spend(self, estimate_usd: float = 0.0) -> None:
        self.checked.append(estimate_usd)
        if self.error is not None:
            raise self.error


class Transport:
    """Answers every request with a clean result using its whole completion allowance."""

    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        prompt = sum(len(m["content"]) // 4 + 1 for m in request.messages)
        return TransportResponse(
            text=json.dumps(answer()),
            finish_reason="stop",
            usage=Usage(prompt, request.max_tokens, 0),
            model=PRICED,
        )


def seeded_client(tmp_path: Path, spent: float, cap: float = 10.0):
    ledger_dir = tmp_path / "spend"
    ledger_dir.mkdir(parents=True)
    if spent:
        line = {
            "at": "2026-09-02T00:00:00Z", "month": "2026-09", "profile": "exe",
            "model": PRICED, "prompt_tokens": 1, "completion_tokens": 1, "usd": spent,
            "usd_known": True, "estimated": False, "tag": "seed", "run": None,
        }
        (ledger_dir / "2026-09.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")
    transport = Transport()
    client = LLMClient(
        Settings(model=PRICED, monthly_usd=cap, max_tokens_per_job=100_000_000),
        transport=transport,
        log=lambda _line: None,
        ledger=SpendLedger(ledger_dir, explicit=True, clock=lambda: SEPT),
    )
    return client, transport


@pytest.mark.intent("AC-continuity-review-11")
def test_estimate_is_every_call_of_the_run_at_its_longest_allowed_answer(repo):
    fake = FakeLLM(lambda call: answer(), model=PRICED)
    estimate = estimate_review(repo, "all", client=fake, env=ENV)
    assert fake.calls == [], "estimating calls no model"

    artifact = review(repo, "all", client=fake, env=ENV, max_workers=1)
    units = [unit for editor in artifact["editors"] for unit in editor["units"]]
    assert units and all(unit["status"] == "reviewed" for unit in units)
    assert estimate.calls == len(fake.calls) == len(units)
    prompt = sum(prompt_token_bound(c.system, c.user, c.schema) for c in fake.calls)
    completion = sum(max(c.max_tokens, REASONING_MIN_MAX_TOKENS) for c in fake.calls)
    assert (estimate.prompt_tokens, estimate.completion_tokens) == (prompt, completion)
    assert estimate.usd == pytest.approx(cap_usd(MODEL_RATES[PRICED], prompt, completion))
    assert estimate.priced and estimate.model == PRICED


@pytest.mark.intent("AC-continuity-review-11")
def test_actual_cost_stays_within_the_estimate_even_when_every_answer_runs_long(repo, tmp_path):
    client, transport = seeded_client(tmp_path, spent=0.0, cap=1000.0)
    estimate = estimate_review(repo, "all", client=client, env=ENV)
    artifact = review(repo, "all", client=client, env=ENV, max_workers=1)
    assert len(transport.requests) == estimate.calls
    assert all(editor["status"] == "ok" for editor in artifact["editors"])
    actual = artifact["llm"]["usd"]
    assert artifact["llm"]["usd_known"] and 0 < actual <= estimate.usd
    assert artifact["llm"]["month_usd"] <= estimate.usd


def test_estimate_of_an_unpriced_model_uses_the_caps_rate_and_says_so(repo):
    estimate = estimate_review(repo, "all", client=FakeLLM(model="house-model"), env=ENV)
    assert not estimate.priced
    assert estimate.usd == pytest.approx(
        cap_usd(UNPRICED_CAP_RATE, estimate.prompt_tokens, estimate.completion_tokens)
    )


def test_estimate_leaves_out_units_too_long_to_send(repo):
    env = {**ENV, "NANOIF_REVIEW_UNIT_BUDGET": "300"}
    fake = FakeLLM(lambda call: answer(), model=PRICED)
    estimate = estimate_review(repo, "all", client=fake, env=env)
    artifact = review(repo, "all", client=fake, env=env, max_workers=1)
    units = [unit for editor in artifact["editors"] for unit in editor["units"]]
    assert any(unit["status"] == "skipped" for unit in units)
    assert estimate.calls == len(fake.calls) > 0


@pytest.mark.intent("AC-continuity-review-35")
def test_all_whose_estimate_does_not_fit_starts_nothing_and_gives_the_cap_reason(repo, tmp_path):
    probe, _ = seeded_client(tmp_path / "probe", spent=0.0)
    estimate = estimate_review(repo, "all", client=probe, env=ENV)
    spent = round(10.0 - estimate.usd / 2, 2)
    assert 0 < spent < 10.0, "the cap is not reached yet; only the estimate does not fit"

    client, transport = seeded_client(tmp_path, spent=spent)
    artifact = review(repo, "all", client=client, env=ENV, max_workers=1)
    validate_artifact(artifact, "ai_review")
    reason = (
        f"monthly AI spend cap reached: ${spent:.2f} of $10.00 in 2026-09 "
        "(resets 2026-10-01 UTC)"
    )
    assert [(e["status"], e["reason"], e["units"]) for e in artifact["editors"]] == [
        ("skipped", reason, []),
        ("skipped", reason, []),
    ]
    assert transport.requests == []
    assert artifact["llm"]["month_cap_reached"] is True


@pytest.mark.intent("AC-continuity-review-35")
def test_changed_and_passage_modes_still_start_when_only_an_estimate_would_not_fit(
    repo, tmp_path
):
    probe, _ = seeded_client(tmp_path / "probe", spent=0.0)
    estimate = estimate_review(repo, "all", client=probe, env=ENV)
    client, transport = seeded_client(tmp_path, spent=round(10.0 - estimate.usd / 2, 2))
    review(repo, "changed", client=client, env=ENV, max_workers=1)
    assert transport.requests, "mode changed keeps the per-call cap (AC-continuity-review-32)"

    fake = SpendRecordingFake(lambda call: answer())
    review(repo, "changed", client=fake, env=ENV, max_workers=1)
    review(repo, "passage", TOLL, client=fake, env=ENV, max_workers=1)
    assert fake.checked == [0.0, 0.0]


@pytest.mark.intent("AC-continuity-review-35")
def test_mode_all_checks_the_cap_for_its_whole_estimate(repo):
    fake = SpendRecordingFake(lambda call: answer(), model=PRICED)
    estimate = estimate_review(repo, "all", client=fake, env=ENV)
    review(repo, "all", client=fake, env=ENV, max_workers=1)
    assert fake.checked == [pytest.approx(estimate.usd)]


@pytest.mark.intent("AC-continuity-review-11", "AC-continuity-review-35")
def test_preflight_estimates_and_checks_the_cap_without_calling_a_model(repo):
    fake = SpendRecordingFake(lambda call: pytest.fail("no model call"), model=PRICED)
    estimate, refused = preflight(repo, "all", client=fake, env=ENV)
    assert refused is None
    assert fake.checked == [pytest.approx(estimate.usd)] and estimate.calls > 0

    reason = "monthly AI spend cap reached: $9.50 of $10.00 in 2026-09 (resets 2026-10-01 UTC)"
    error = LLMSpendCapReached("capped", reason=reason, month_usd=9.5, cap_usd=10.0)
    capped = SpendRecordingFake(lambda call: pytest.fail("no model call"), error=error)
    _estimate, refused = preflight(repo, "all", client=capped, env=ENV)
    assert refused is not None
    validate_artifact(refused, "ai_review")
    assert refused["mode"] == "all"
    assert [(e["status"], e["reason"]) for e in refused["editors"]] == [("skipped", reason)] * 2
    assert capped.calls == []


def test_estimate_summary_and_outputs_round_up_and_say_it_is_an_upper_bound(repo):
    estimate = estimate_review(repo, "all", client=FakeLLM(model=PRICED), env=ENV)
    line = estimate.summary()
    shown = re.match(r"estimated cost: at most \$(\d+\.\d\d) for (\d+) model calls", line)
    assert shown is not None, line
    assert estimate.usd <= float(shown.group(1)) < estimate.usd + 0.01
    assert int(shown.group(2)) == estimate.calls
    assert f"{PRICED} list prices" in line
    unpriced = estimate_review(repo, "all", client=FakeLLM(model="house-model"), env=ENV)
    assert "no known price" in unpriced.summary()
    outputs = estimate.outputs()
    assert set(outputs) == {"estimate_usd", "estimate_calls", "estimate_priced"}
    assert estimate.usd <= float(outputs["estimate_usd"]) < estimate.usd + 0.0001
    assert (outputs["estimate_calls"], outputs["estimate_priced"]) == (str(estimate.calls), "true")
    assert unpriced.outputs()["estimate_priced"] == "false"
