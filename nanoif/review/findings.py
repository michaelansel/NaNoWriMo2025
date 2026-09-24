"""Findings shared by the editors: identity, quote verification, severity, merging.

A finding's key is ``f-`` plus the first 8 hex digits of ``sha256("type|a|b")`` where
``a`` and ``b`` are the two passage names sorted (``a == b`` for single-passage findings),
so the same contradiction reported from several review units, or on the next run, has the
same key and can be merged or dismissed.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from nanoif.review.units import ReviewStory, ReviewUnit
from nanoif.twee.files import relative_file
from nanoif.twee.links import display_text

SEVERITIES = ("minor", "major", "critical")
CONFIDENCES = ("low", "medium", "high")

_QUOTE_CHARS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class PassageRef:
    """A passage a finding was made against.

    Attributes:
        name: Passage name.
        hash: Content hash of the passage text the finding saw.
        file: Repository-relative source file, when known.
        line: 1-based header line, when known.
    """

    name: str
    hash: str
    file: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class Quote:
    """A verbatim quote and the passage it comes from."""

    passage: str
    text: str


@dataclass(frozen=True)
class Finding:
    """One reported problem, after post-processing.

    Attributes:
        key: Stable identity, see :func:`finding_key`.
        editor: ``continuity`` or ``style``.
        type: Finding type from the editor's schema.
        severity: ``minor``, ``major`` or ``critical``, computed by code.
        confidence: ``low``, ``medium`` or ``high``.
        description: What is wrong, for a writer.
        passages: The passage under review first, then the other passage (if any).
        quotes: Verbatim quotes with passage names.
        canon_fact_id: The canon fact involved, for canon findings.
        routes_seen: How many review units reported this key.
    """

    key: str
    editor: str
    type: str
    severity: str
    confidence: str
    description: str
    passages: tuple[PassageRef, ...]
    quotes: tuple[Quote, ...]
    canon_fact_id: str | None = None
    routes_seen: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize in the ``ai_review`` artifact's finding shape."""
        return {
            "key": self.key,
            "editor": self.editor,
            "type": self.type,
            "severity": self.severity,
            "confidence": self.confidence,
            "description": self.description,
            "passages": [
                {"name": ref.name, "hash": ref.hash, "file": ref.file, "line": ref.line}
                for ref in self.passages
            ],
            "quotes": [{"passage": quote.passage, "text": quote.text} for quote in self.quotes],
            "canon_fact_id": self.canon_fact_id,
            "routes_seen": self.routes_seen,
        }


@dataclass
class UnitFindings:
    """What one unit's answer yields after post-processing.

    Attributes:
        findings: Findings whose quotes all verified.
        unverified: Findings with a quote not found in its passage (never shown as findings).
        dropped: Findings discarded as malformed (not involving the passage under review,
            citing a third passage, or naming an unknown passage or fact).
    """

    findings: list[Finding] = field(default_factory=list)
    unverified: list[Finding] = field(default_factory=list)
    dropped: int = 0


def finding_key(finding_type: str, a: str, b: str) -> str:
    """Return the stable key of a finding.

    Args:
        finding_type: The finding type.
        a: One passage name.
        b: The other passage name (the same name for single-passage findings).

    Returns:
        ``f-`` and 8 hex digits; independent of the order of ``a`` and ``b``.
    """
    first, second = sorted((a, b))
    digest = hashlib.sha256(f"{finding_type}|{first}|{second}".encode()).hexdigest()
    return f"f-{digest[:8]}"


def normalize_text(text: str) -> str:
    """Normalize for quote matching: typographic quotes to plain, whitespace collapsed.

    Args:
        text: Any text.

    Returns:
        The normalized text.
    """
    return _SPACE_RE.sub(" ", text.translate(_QUOTE_CHARS)).strip()


def clean_quote(text: str) -> str:
    """Strip surrounding whitespace and double quotation marks a model wraps a quote in.

    Args:
        text: The quote as the model wrote it.

    Returns:
        The quote itself.
    """
    return text.strip().strip('"“”').strip()


def quote_found(quote: str, texts: Iterable[str]) -> bool:
    """Return whether a quote is a whitespace-normalized substring of any of ``texts``.

    Args:
        quote: The quote.
        texts: Renderings of the cited passage.

    Returns:
        True when found; an empty quote is never found.
    """
    needle = normalize_text(clean_quote(quote))
    if not needle:
        return False
    return any(needle in normalize_text(text) for text in texts)


def passage_texts(story: ReviewStory, name: str, unit: ReviewUnit | None = None) -> list[str]:
    """Return every rendering of a passage a quote may legitimately come from.

    Args:
        story: The story.
        name: The passage.
        unit: The unit the model saw, whose rendering (with ``[unselected]``) counts too.

    Returns:
        Raw text, text with every link as prose, and the unit rendering when present.
    """
    raw = story.content[name]
    texts = [raw, display_text(raw)]
    if unit is not None:
        texts.extend(entry.text for entry in unit.passages if entry.name == name)
    return texts


def passage_ref(story: ReviewStory, name: str) -> PassageRef:
    """Build the reference to a passage, with its hash and declaration site.

    Args:
        story: The story.
        name: The passage.

    Returns:
        The reference; file and line are ``None`` when the source site is unknown.
    """
    location = story.locations.get(name)
    if location is None:
        return PassageRef(name=name, hash=story.hash(name))
    file = location.file.as_posix()
    if story.repo is not None and location.file.is_relative_to(story.repo.resolve()):
        file = relative_file(location, story.repo)
    return PassageRef(name=name, hash=story.hash(name), file=file, line=location.line)


def clamp_severity(severity: str, bounds: tuple[str, str]) -> str:
    """Clamp a severity into ``bounds``; the type decides the range, never the model alone.

    Args:
        severity: The rubric answer.
        bounds: ``(lowest, highest)`` allowed for the finding type.

    Returns:
        The final severity.
    """
    low, high = (SEVERITIES.index(bound) for bound in bounds)
    rank = SEVERITIES.index(severity) if severity in SEVERITIES else low
    return SEVERITIES[min(max(rank, low), high)]


def _stronger(values: Sequence[str], a: str, b: str) -> str:
    return a if values.index(a) >= values.index(b) else b


def merge_findings(per_unit: Iterable[Iterable[Finding]]) -> list[Finding]:
    """Merge findings with the same key across review units.

    Quotes are unioned in first-seen order, ``routes_seen`` counts the units that reported
    the key, and the highest severity and confidence win. The description and passage
    references of the first report are kept.

    Args:
        per_unit: Each unit's findings, in unit order.

    Returns:
        One finding per key, most severe first, then in first-seen order.
    """
    merged: dict[str, Finding] = {}
    seen_in: dict[str, set[int]] = {}
    for index, findings in enumerate(per_unit):
        for finding in findings:
            seen_in.setdefault(finding.key, set()).add(index)
            current = merged.get(finding.key)
            if current is None:
                merged[finding.key] = finding
                continue
            quotes = list(current.quotes)
            known = {(q.passage, normalize_text(q.text)) for q in quotes}
            for quote in finding.quotes:
                if (quote.passage, normalize_text(quote.text)) not in known:
                    quotes.append(quote)
                    known.add((quote.passage, normalize_text(quote.text)))
            merged[finding.key] = replace(
                current,
                quotes=tuple(quotes),
                severity=_stronger(SEVERITIES, current.severity, finding.severity),
                confidence=_stronger(CONFIDENCES, current.confidence, finding.confidence),
            )
    order = list(merged)
    result = [replace(merged[key], routes_seen=len(seen_in[key])) for key in order]
    result.sort(key=lambda f: (-SEVERITIES.index(f.severity), order.index(f.key)))
    return result


def is_dismissed(finding: Finding, dismissals: Mapping[str, Sequence[Mapping[str, str]]]) -> bool:
    """Return whether a dismissal covers this finding at its current passage hashes.

    Args:
        finding: The finding.
        dismissals: Key to the recorded ``{passage name: hash}`` maps for that key.

    Returns:
        True when some dismissal of this key recorded the same hash for every passage.
    """
    for hashes in dismissals.get(finding.key, ()):
        if all(hashes.get(ref.name) == ref.hash for ref in finding.passages):
            return True
    return False
