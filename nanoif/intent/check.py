"""Consistency checks between intent documents and the tests that prove them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nanoif.intent.docs import load_index, scan_citations


@dataclass(frozen=True)
class Finding:
    """One problem in the intent record."""

    level: str
    code: str
    file: str
    line: int | None
    message: str

    def render(self) -> str:
        """Return ``file:line: level code: message``."""
        where = f"{self.file}:{self.line}" if self.line else self.file
        return f"{where}: {self.level} {self.code}: {self.message}"


def check_repo(repo: Path) -> list[Finding]:
    """Check criteria, ADRs, and test citations under ``repo``.

    Args:
        repo: Repository root.

    Returns:
        Findings sorted by file and line; any ``error`` fails the gate.
    """
    index = load_index(repo)
    citations = scan_citations(repo)
    findings: list[Finding] = []

    for rel, count in index.feature_files.items():
        if count == 0:
            findings.append(
                Finding("error", "no-criteria", rel, None,
                        "feature note declares no acceptance criteria (- AC-<name>-<n>: ...)")
            )
    for criterion in index.criteria.values():
        expected = Path(criterion.file).stem
        if criterion.slug != expected:
            findings.append(
                Finding("error", "criterion-prefix", criterion.file, criterion.line,
                        f"{criterion.id} must be named AC-{expected}-<n> in this file")
            )
        if criterion.verify == "test" and criterion.id not in citations:
            findings.append(
                Finding("error", "untested-criterion", criterion.file, criterion.line,
                        f"{criterion.id} has no test citing it; add "
                        f'@pytest.mark.intent("{criterion.id}") '
                        "or mark it (verify: workflow|manual)")
            )
    for duplicate in index.duplicates:
        first = index.criteria[duplicate.id]
        findings.append(
            Finding("error", "duplicate-criterion", duplicate.file, duplicate.line,
                    f"{duplicate.id} already declared at {first.file}:{first.line}")
        )
    for cited, sites in citations.items():
        if cited in index.criteria or cited in index.adrs:
            continue
        for site in sites:
            findings.append(
                Finding("error", "unknown-citation", site.file, site.line,
                        f"{site.test} cites {cited}, which no feature note or ADR declares")
            )
    for adr in index.adrs.values():
        if not adr.status:
            findings.append(Finding("error", "adr-status", adr.file, None,
                                    f"{adr.id} has no 'Status:' line"))
        if adr.superseded_by and adr.superseded_by not in index.adrs:
            findings.append(
                Finding("error", "dangling-supersede", adr.file, None,
                        f"{adr.id} is superseded by {adr.superseded_by}, which does not exist")
            )
    return sorted(findings, key=lambda f: (f.file, f.line or 0, f.code))
