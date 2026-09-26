"""The monthly spend ledger behind the self-imposed AI spend cap (ADR-023).

One append-only JSONL file per UTC month, ``<dir>/YYYY-MM.jsonl``, one line per provider
response or charged failure. This module is the only code that reads or writes it. The
ledger fails closed: a line that cannot be read or does not match its schema raises
:class:`LLMLedgerError` naming ``path:line``, and is never counted as zero spend.

Reads are incremental: the first read of a month parses the whole file, later reads parse
only the bytes appended since, so spend written by another process is counted without
re-reading the file on every call.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from nanoif.errors import ArtifactValidationError
from nanoif.llm.errors import LLMConfigError, LLMLedgerError
from nanoif.schemas.artifacts import validate_artifact

LEDGER_DIR_ENV = "NANOIF_LLM_LEDGER_DIR"
SCHEMA = "spend_ledger_line"


def utc_now() -> datetime:
    """The current time in UTC."""
    return datetime.now(UTC)


def resolve_ledger_dir(env: Mapping[str, str] | None = None) -> tuple[Path, bool]:
    """Return the ledger directory and whether it was set explicitly.

    Args:
        env: Mapping to read; defaults to ``os.environ``.

    Returns:
        ``(directory, explicit)``: ``NANOIF_LLM_LEDGER_DIR`` when set, else
        ``$XDG_STATE_HOME/nanoif/spend`` (or ``~/.local/state/nanoif/spend``).
    """
    env = os.environ if env is None else env
    explicit = env.get(LEDGER_DIR_ENV, "").strip()
    if explicit:
        return Path(explicit).expanduser(), True
    state = env.get("XDG_STATE_HOME", "").strip()
    base = Path(state).expanduser() if state else Path.home() / ".local" / "state"
    return base / "nanoif" / "spend", False


def next_month_start(month: str) -> str:
    """Return the first day of the month after ``YYYY-MM``, as ``YYYY-MM-01``."""
    year, number = (int(part) for part in month.split("-"))
    year, number = (year + 1, 1) if number == 12 else (year, number + 1)
    return f"{year:04d}-{number:02d}-01"


def spend_line(summary: Mapping[str, object]) -> str | None:
    """The step-summary line for a ``usage_summary()``, or ``None`` without a spend ledger.

    Args:
        summary: ``LLMClient.usage_summary()`` output (test doubles have no ``month``).

    Returns:
        For example ``monthly AI spend: $3.14 of $10.00 in 2026-11``.
    """
    month = summary.get("month")
    if not month:
        return None
    usd, cap = summary.get("month_usd"), summary.get("month_cap_usd")
    if not isinstance(usd, (int, float)):
        return f"monthly AI spend: unknown in {month} (spend ledger unreadable)"
    if not isinstance(cap, (int, float)):
        return f"monthly AI spend: ${usd:.2f} in {month} (cap off)"
    return f"monthly AI spend: ${usd:.2f} of ${cap:.2f} in {month}"


@dataclass(frozen=True)
class MonthSpend:
    """Estimated spend recorded in one month.

    Attributes:
        month: ``YYYY-MM`` (UTC).
        usd: Sum of ``usd`` over the month's lines.
        known: ``False`` when any line was charged at the unpriced fallback rate.
    """

    month: str
    usd: float
    known: bool


class SpendLedger:
    """Month-scoped, append-only spend ledger shared by every process on one machine.

    Args:
        directory: Where the ``YYYY-MM.jsonl`` files live.
        explicit: The directory was configured; a missing one is then an error rather
            than created, so a lost directory never silently restarts the month at zero.
        clock: Returns the current UTC time; tests pass a fixed one.

    Raises:
        LLMConfigError: ``explicit`` and the directory does not exist, or it cannot be
            created.
    """

    def __init__(
        self,
        directory: Path,
        *,
        explicit: bool,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if explicit and not directory.is_dir():
            raise LLMConfigError(
                f"{LEDGER_DIR_ENV} {directory} does not exist; create it or unset the variable"
            )
        if not explicit:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise LLMConfigError(
                    f"cannot create spend ledger directory {directory}: {exc}"
                ) from exc
        self.directory = directory
        self._clock = clock
        self._lock = threading.Lock()
        self._month = ""
        self._offset = 0
        self._lines = 0
        self._usd = 0.0
        self._known = True

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, clock: Callable[[], datetime] = utc_now
    ) -> SpendLedger:
        """Open the ledger configured by the environment (see :func:`resolve_ledger_dir`)."""
        directory, explicit = resolve_ledger_dir(env)
        return cls(directory, explicit=explicit, clock=clock)

    def month(self) -> str:
        """The current UTC month, ``YYYY-MM``."""
        return self._clock().astimezone(UTC).strftime("%Y-%m")

    def path(self, month: str) -> Path:
        """The ledger file for ``month``."""
        return self.directory / f"{month}.jsonl"

    def month_to_date(self) -> MonthSpend:
        """Return this month's spend, including lines appended by other processes.

        Raises:
            LLMLedgerError: A line is not JSON or does not match the ledger schema, or the
                file cannot be read.
        """
        with self._lock:
            self._refresh()
            return MonthSpend(self._month, self._usd, self._known)

    def append(
        self,
        *,
        profile: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        usd: float,
        usd_known: bool,
        estimated: bool,
        tag: str,
        run: str | None,
    ) -> None:
        """Append one charged call to this month's file.

        Raises:
            LLMLedgerError: The line does not validate or cannot be written.
        """
        now = self._clock().astimezone(UTC)
        entry = {
            "at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "month": now.strftime("%Y-%m"),
            "profile": profile,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "usd": round(usd, 8),
            "usd_known": usd_known,
            "estimated": estimated,
            "tag": tag,
            "run": run,
        }
        try:
            validate_artifact(entry, SCHEMA)
        except ArtifactValidationError as exc:
            raise LLMLedgerError(str(exc), reason=f"spend ledger line rejected: {exc}") from exc
        path = self.path(entry["month"])
        data = (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8")
        with self._lock:
            try:
                with path.open("ab") as fh:
                    fcntl.flock(fh, fcntl.LOCK_EX)
                    try:
                        fh.write(data)
                        fh.flush()
                        os.fsync(fh.fileno())
                    finally:
                        fcntl.flock(fh, fcntl.LOCK_UN)
            except OSError as exc:
                raise LLMLedgerError(
                    f"cannot append to {path}: {exc}",
                    reason=f"spend ledger could not be written: {path}: {exc}",
                ) from exc

    # -- internals -----------------------------------------------------------------

    def _refresh(self) -> None:
        month = self.month()
        if month != self._month:
            self._month, self._offset, self._lines = month, 0, 0
            self._usd, self._known = 0.0, True
        path = self.path(month)
        try:
            with path.open("rb") as fh:
                fcntl.flock(fh, fcntl.LOCK_SH)
                try:
                    fh.seek(self._offset)
                    chunk = fh.read()
                finally:
                    fcntl.flock(fh, fcntl.LOCK_UN)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise LLMLedgerError(
                f"cannot read {path}: {exc}", reason=f"spend ledger unreadable: {path}: {exc}"
            ) from exc
        # Only complete lines count; a line still being written is read next time.
        complete = chunk[: chunk.rfind(b"\n") + 1]
        for raw in complete.splitlines():
            number = self._lines + 1
            where = f"{path}:{number}"
            try:
                entry = json.loads(raw)
                validate_artifact(entry, SCHEMA)
            except (ValueError, ArtifactValidationError) as exc:
                raise LLMLedgerError(
                    f"{where}: {exc}", reason=f"spend ledger unreadable: {where}: {exc}"
                ) from exc
            self._lines = number
            self._usd += float(entry["usd"])
            self._known = self._known and bool(entry["usd_known"])
        self._offset += len(complete)
