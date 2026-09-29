"""The shared stage-1 extraction store: one ``bible_extract`` answer per key (ADR-026).

This module is the only code that reads or writes the store. An entry is
``<dir>/<key[:2]>/<key>.json`` (schema ``extract_store_entry``), where ``key`` is the
SHA-256 of the canonical JSON of the key fields: passage name, content hash, prompt and
schema hashes, profile, model, reasoning effort and ``max_tokens``. The roster and the
``not-entity:`` phrases are left out on purpose (AC-story-bible-36): resolve on ``main``
realigns names, and assemble removes not-entities.

The store never raises. A file that cannot be read, is not JSON, fails its schema, was
written under other key fields, or holds an answer the current prompt schema rejects is a
miss counted ``invalid``, with a warning that names the path. A failed write is counted
``write_failed``. A directory that cannot be created or read makes the store
``unavailable``: every lookup is a miss and nothing is written. Losing the store costs
money, never correctness. Warnings are collected in :attr:`ExtractStore.warnings`; the CLI
decides how to show them.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from nanoif.errors import ArtifactValidationError
from nanoif.llm.errors import LLMConfigError, LLMSchemaError
from nanoif.llm.ledger import utc_now
from nanoif.llm.prompts import prompt_hash, prompt_schema, schema_hash
from nanoif.llm.schema import validate
from nanoif.schemas.artifacts import validate_artifact

STORE_DIR_ENV = "NANOIF_BIBLE_STORE_DIR"
SCHEMA = "extract_store_entry"
PROMPT = "bible_extract"
ENTRY_VERSION = 1


def resolve_store_dir(env: Mapping[str, str] | None = None) -> Path:
    """Return the store directory.

    Args:
        env: Mapping to read; defaults to ``os.environ``.

    Returns:
        ``NANOIF_BIBLE_STORE_DIR`` when set, else ``$XDG_STATE_HOME/nanoif/extract-store``
        (or ``~/.local/state/nanoif/extract-store``).
    """
    env = os.environ if env is None else env
    explicit = env.get(STORE_DIR_ENV, "").strip()
    if explicit:
        return Path(explicit).expanduser()
    state = env.get("XDG_STATE_HOME", "").strip()
    base = Path(state).expanduser() if state else Path.home() / ".local" / "state"
    return base / "nanoif" / "extract-store"


@dataclass(frozen=True)
class StoreKey:
    """The fields that decide a ``bible_extract`` answer, and the key derived from them.

    Attributes:
        passage_name: The passage.
        content_hash: Its text's hash (``nanoif.twee`` passage hash).
        prompt_hash: ``prompt_hash("bible_extract")``.
        schema_hash: ``schema_hash("bible_extract")``.
        profile: The inference profile.
        model: The model id.
        reasoning_effort: The effort sent with the call.
        max_tokens: The completion cap sent with the call.
    """

    passage_name: str
    content_hash: str
    prompt_hash: str
    schema_hash: str
    profile: str
    model: str
    reasoning_effort: str | None
    max_tokens: int

    @classmethod
    def build(
        cls,
        *,
        passage_name: str,
        content_hash: str,
        profile: str,
        model: str,
        reasoning_effort: str | None,
        max_tokens: int,
    ) -> StoreKey:
        """Build a key with the current ``bible_extract`` prompt and schema hashes.

        Args:
            passage_name: The passage.
            content_hash: Its text's hash.
            profile: The inference profile.
            model: The model id.
            reasoning_effort: The effort sent with the call.
            max_tokens: The completion cap sent with the call.

        Returns:
            The key.
        """
        return cls(
            passage_name=passage_name,
            content_hash=content_hash,
            prompt_hash=prompt_hash(PROMPT),
            schema_hash=schema_hash(PROMPT),
            profile=profile,
            model=model,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
        )

    def fields(self) -> dict[str, Any]:
        """The key fields, as stored in an entry's ``key_fields``."""
        return asdict(self)

    @property
    def digest(self) -> str:
        """SHA-256 hex of the canonical JSON of :meth:`fields`."""
        canonical = json.dumps(
            self.fields(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def bypassed_report(reason: str) -> dict[str, Any]:
    """The ``store`` block of a run that used no store at all.

    Args:
        reason: Why the store was not used.

    Returns:
        ``{status: bypassed, hits: [], misses: 0, invalid: 0, write_failed: 0, reason}``.
    """
    return {
        "status": "bypassed",
        "hits": [],
        "misses": 0,
        "invalid": 0,
        "write_failed": 0,
        "reason": reason,
    }


class ExtractStore:
    """A directory of stored ``bible_extract`` answers, with this run's accounting.

    Use :meth:`open`, which never raises. Lookups and saves are thread-safe.

    Args:
        directory: The store directory.
        unavailable: Why the directory cannot be used, or ``""``.
        run: ``GITHUB_RUN_ID`` recorded with every entry written.
        clock: Returns the current UTC time.
    """

    def __init__(
        self,
        directory: Path,
        *,
        unavailable: str = "",
        run: str | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.directory = directory
        self.unavailable = unavailable
        self._run = run
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: list[str] = []
        self._misses = 0
        self._invalid = 0
        self._write_failed = 0
        self.warnings: list[str] = []

    @classmethod
    def open(
        cls,
        directory: Path,
        *,
        run: str | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> ExtractStore:
        """Open the store, creating the directory when it is missing.

        Args:
            directory: The store directory (see :func:`resolve_store_dir`).
            run: Recorded with each entry; defaults to ``GITHUB_RUN_ID``.
            clock: Returns the current UTC time; tests pass a fixed one.

        Returns:
            The store; ``unavailable`` when the directory cannot be created or read.
        """
        run = run if run is not None else os.environ.get("GITHUB_RUN_ID") or None
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            reason = f"extraction store {directory} cannot be created: {exc}"
            return cls(directory, unavailable=reason, run=run, clock=clock)
        if not os.access(directory, os.R_OK | os.W_OK | os.X_OK):
            reason = f"extraction store {directory} cannot be read and written"
            return cls(directory, unavailable=reason, run=run, clock=clock)
        return cls(directory, run=run, clock=clock)

    def path(self, key: StoreKey) -> Path:
        """Return where the entry for ``key`` lives."""
        digest = key.digest
        return self.directory / digest[:2] / f"{digest}.json"

    def lookup(self, key: StoreKey) -> dict[str, Any] | None:
        """Return the stored answer for ``key``, or ``None`` on a miss.

        A hit needs a file that parses and validates, whose ``key_fields`` equal the
        requested ones, and whose ``answer`` validates against the current
        ``bible_extract`` schema. Anything else is a miss, counted ``invalid`` with a
        warning when the file exists.

        Args:
            key: The request's key.

        Returns:
            The raw answer, for the caller to filter against the current text.
        """
        if self.unavailable:
            self._miss()
            return None
        path = self.path(key)
        if not path.exists():
            self._miss()
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            return self._reject(path, f"cannot be read: {exc}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return self._reject(path, f"is not valid JSON: {exc}")
        try:
            validate_artifact(data, SCHEMA)
        except ArtifactValidationError as exc:
            return self._reject(path, f"fails its schema: {exc}")
        if data["key_fields"] != key.fields():
            return self._reject(path, "was written for other key fields")
        try:
            validate(data["answer"], prompt_schema(PROMPT))
        except (LLMSchemaError, LLMConfigError) as exc:
            return self._reject(path, f"holds an answer the current {PROMPT} schema rejects: {exc}")
        with self._lock:
            self._hits.append(key.passage_name)
        return data["answer"]

    def save(self, key: StoreKey, answer: Mapping[str, Any]) -> bool:
        """Write an answer atomically (temporary file in the same directory, then rename).

        Args:
            key: The request's key.
            answer: The raw, schema-valid ``bible_extract`` answer.

        Returns:
            Whether the entry was written; a failure is counted and warned, never raised.
        """
        if self.unavailable:
            return False
        path = self.path(key)
        entry = {
            "version": ENTRY_VERSION,
            "key_fields": key.fields(),
            "answer": answer,
            "created_at": self._clock().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run": self._run,
        }
        temp: Path | None = None
        try:
            text = json.dumps(entry, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            validate_artifact(entry, SCHEMA)
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
            ) as handle:
                temp = Path(handle.name)
                handle.write(text)
            os.replace(temp, path)
        except (OSError, TypeError, ValueError, ArtifactValidationError) as exc:
            # TypeError and ValueError are what json.dumps raises for non-JSON data.
            if temp is not None:
                temp.unlink(missing_ok=True)
            with self._lock:
                self._write_failed += 1
                self.warnings.append(
                    f"extraction store: could not save the answer for {key.passage_name!r} "
                    f"to {path}: {exc}"
                )
            return False
        return True

    def report(self, *, read: bool = True, reason: str = "") -> dict[str, Any]:
        """The ``store`` block of ``bible_diff``.

        Args:
            read: Whether this run looked answers up; ``False`` (``--full``) reports
                ``bypassed`` unless the store was unavailable.
            reason: Why the store was not read, with ``read=False``.

        Returns:
            ``{status: used|unavailable|bypassed, hits: [passage], misses, invalid,
            write_failed, reason}``.
        """
        with self._lock:
            if self.unavailable:
                status, why = "unavailable", self.unavailable
            elif not read:
                status, why = "bypassed", reason
            else:
                status, why = "used", ""
            return {
                "status": status,
                "hits": sorted(self._hits),
                "misses": self._misses,
                "invalid": self._invalid,
                "write_failed": self._write_failed,
                "reason": why,
            }

    def _miss(self) -> None:
        with self._lock:
            self._misses += 1

    def _reject(self, path: Path, why: str) -> None:
        with self._lock:
            self._misses += 1
            self._invalid += 1
            self.warnings.append(f"extraction store entry {path} {why}; extracting again")
        return None
