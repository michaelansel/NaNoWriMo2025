"""The monthly spend ledger: one JSONL file per UTC month, read incrementally, failing closed."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nanoif.llm.errors import LLMConfigError, LLMLedgerError
from nanoif.llm.ledger import SpendLedger, next_month_start, resolve_ledger_dir, spend_line

SEPT = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def at(moment: datetime):
    return lambda: moment


def line(usd: float, *, month: str = "2026-09", known: bool = True, **extra) -> dict:
    entry = {
        "at": f"{month}-02T00:00:00Z",
        "month": month,
        "profile": "exe",
        "model": "fireworks/gpt-oss-120b",
        "prompt_tokens": 100,
        "completion_tokens": 10,
        "usd": usd,
        "usd_known": known,
        "estimated": False,
        "tag": "continuity:Start",
        "run": None,
    }
    entry.update(extra)
    return entry


def write_lines(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def test_default_directory_is_created_under_xdg_state_home(isolated_spend_ledger):
    directory, explicit = resolve_ledger_dir({"XDG_STATE_HOME": str(isolated_spend_ledger.parents[1])})
    assert directory == isolated_spend_ledger and explicit is False
    SpendLedger(directory, explicit=False, clock=at(SEPT)).month_to_date()
    assert directory.is_dir()


def test_explicit_directory_that_is_missing_is_a_config_error(tmp_path):
    directory, explicit = resolve_ledger_dir({"NANOIF_LLM_LEDGER_DIR": str(tmp_path / "gone")})
    assert explicit is True
    with pytest.raises(LLMConfigError, match="NANOIF_LLM_LEDGER_DIR"):
        SpendLedger(directory, explicit=True, clock=at(SEPT))


def test_month_to_date_sums_only_the_current_month(tmp_path):
    write_lines(tmp_path / "2026-08.jsonl", [line(9.0, month="2026-08")])
    write_lines(tmp_path / "2026-09.jsonl", [line(0.5), line(0.25)])
    spend = SpendLedger(tmp_path, explicit=True, clock=at(SEPT)).month_to_date()
    assert spend.month == "2026-09"
    assert spend.usd == pytest.approx(0.75)
    assert spend.known is True


def test_appended_lines_are_counted_and_validated(tmp_path):
    ledger = SpendLedger(tmp_path, explicit=True, clock=at(SEPT))
    ledger.append(
        profile="exe", model="m", prompt_tokens=10, completion_tokens=2, usd=0.01,
        usd_known=False, estimated=True, tag="t", run="42",
    )
    spend = ledger.month_to_date()
    assert spend.usd == pytest.approx(0.01) and spend.known is False
    stored = json.loads((tmp_path / "2026-09.jsonl").read_text().strip())
    assert stored["month"] == "2026-09" and stored["run"] == "42" and stored["estimated"] is True


def test_spend_written_by_another_process_is_picked_up(tmp_path):
    mine = SpendLedger(tmp_path, explicit=True, clock=at(SEPT))
    assert mine.month_to_date().usd == 0
    write_lines(tmp_path / "2026-09.jsonl", [line(1.5)])
    assert mine.month_to_date().usd == pytest.approx(1.5)
    write_lines(tmp_path / "2026-09.jsonl", [line(0.5)])
    assert mine.month_to_date().usd == pytest.approx(2.0)


def test_a_new_month_starts_from_its_own_file(tmp_path):
    moments = [SEPT, datetime(2026, 10, 1, 0, 0, 1, tzinfo=UTC)]
    ledger = SpendLedger(tmp_path, explicit=True, clock=lambda: moments[0])
    write_lines(tmp_path / "2026-09.jsonl", [line(3.0)])
    assert ledger.month_to_date().usd == pytest.approx(3.0)
    moments[0] = moments[1]
    spend = ledger.month_to_date()
    assert spend.month == "2026-10" and spend.usd == 0


@pytest.mark.intent("AC-continuity-review-33")
def test_unreadable_line_fails_closed_naming_file_and_line(tmp_path):
    path = tmp_path / "2026-09.jsonl"
    write_lines(path, [line(0.5)])
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    with pytest.raises(LLMLedgerError, match=r"2026-09\.jsonl:2"):
        SpendLedger(tmp_path, explicit=True, clock=at(SEPT)).month_to_date()


@pytest.mark.intent("AC-continuity-review-33")
def test_line_that_breaks_the_schema_fails_closed(tmp_path):
    write_lines(tmp_path / "2026-09.jsonl", [line(-1.0)])
    with pytest.raises(LLMLedgerError, match=r"2026-09\.jsonl:1"):
        SpendLedger(tmp_path, explicit=True, clock=at(SEPT)).month_to_date()


def test_next_month_start():
    assert next_month_start("2026-09") == "2026-10-01"
    assert next_month_start("2026-12") == "2027-01-01"


@pytest.mark.parametrize(
    ("summary", "line"),
    [
        (
            {"month": "2026-11", "month_usd": 3.14159, "month_cap_usd": 10.0},
            "monthly AI spend: $3.14 of $10.00 in 2026-11",
        ),
        (
            {"month": "2026-11", "month_usd": 3.0, "month_cap_usd": None},
            "monthly AI spend: $3.00 in 2026-11 (cap off)",
        ),
        (
            {"month": "2026-11", "month_usd": None, "month_cap_usd": 10.0},
            "monthly AI spend: unknown in 2026-11 (spend ledger unreadable)",
        ),
        ({"profile": "fake"}, None),
    ],
)
def test_spend_line_for_step_summaries(summary, line):
    assert spend_line(summary) == line
