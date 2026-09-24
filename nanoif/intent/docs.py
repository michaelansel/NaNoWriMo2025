"""Parse acceptance criteria, ADRs, and test citations from the repository."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

CRITERION_RE = re.compile(
    r"^\s*[-*]\s+(?P<id>AC-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)-(?P<n>\d+))\s*:\s*(?P<text>.+?)\s*$"
)
VERIFY_RE = re.compile(r"\(verify:\s*(?P<how>test|workflow|manual)\)\s*$")
ADR_FILE_RE = re.compile(r"^(?P<n>\d{3})-[a-z0-9-]+\.md$")
ADR_STATUS_RE = re.compile(r"^\s*\**Status\**\s*:\s*\**\s*(?P<status>.+?)\s*\**\s*$", re.MULTILINE)
SUPERSEDED_RE = re.compile(r"Superseded by (?P<id>ADR-\d{3})")


@dataclass(frozen=True)
class Criterion:
    """One acceptance criterion from a feature note."""

    id: str
    slug: str
    file: str
    line: int
    text: str
    verify: str


@dataclass(frozen=True)
class Adr:
    """One architecture decision record."""

    id: str
    file: str
    status: str | None
    superseded_by: str | None


@dataclass(frozen=True)
class Citation:
    """A test that claims to prove a criterion."""

    id: str
    file: str
    line: int
    test: str


@dataclass
class IntentIndex:
    """Everything the intent documents declare.

    Attributes:
        criteria: Criterion id to its first declaration.
        duplicates: Later declarations of an id already seen.
        feature_files: Every ``features/*.md`` path with the number of criteria in it.
        adrs: ADR id to record.
    """

    criteria: dict[str, Criterion] = field(default_factory=dict)
    duplicates: list[Criterion] = field(default_factory=list)
    feature_files: dict[str, int] = field(default_factory=dict)
    adrs: dict[str, Adr] = field(default_factory=dict)


def load_index(repo: Path) -> IntentIndex:
    """Read ``features/*.md`` and ``architecture/NNN-*.md`` under ``repo``.

    Args:
        repo: Repository root.

    Returns:
        The parsed index. Malformed content is recorded, not raised; :func:`check_repo`
        turns it into findings.
    """
    index = IntentIndex()
    features = repo / "features"
    for path in sorted(features.glob("*.md")) if features.is_dir() else []:
        rel = path.relative_to(repo).as_posix()
        count = 0
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = CRITERION_RE.match(line)
            if not match:
                continue
            count += 1
            text = match["text"]
            verify = VERIFY_RE.search(text)
            criterion = Criterion(
                id=match["id"],
                slug=match["slug"],
                file=rel,
                line=number,
                text=VERIFY_RE.sub("", text).strip(),
                verify=verify["how"] if verify else "test",
            )
            if criterion.id in index.criteria:
                index.duplicates.append(criterion)
            else:
                index.criteria[criterion.id] = criterion
        index.feature_files[rel] = count
    architecture = repo / "architecture"
    for path in sorted(architecture.glob("*.md")) if architecture.is_dir() else []:
        match = ADR_FILE_RE.match(path.name)
        if not match:
            continue
        text = path.read_text(encoding="utf-8")
        status = ADR_STATUS_RE.search(text)
        status_text = status["status"] if status else None
        superseded = SUPERSEDED_RE.search(status_text or "")
        adr_id = f"ADR-{match['n']}"
        index.adrs[adr_id] = Adr(
            id=adr_id,
            file=path.relative_to(repo).as_posix(),
            status=status_text,
            superseded_by=superseded["id"] if superseded else None,
        )
    return index


def scan_citations(repo: Path) -> dict[str, list[Citation]]:
    """Find ``@pytest.mark.intent("AC-...", ...)`` markers in ``tests/``.

    Args:
        repo: Repository root.

    Returns:
        Cited id to the tests citing it. Files that do not parse are skipped; pytest
        itself reports them.
    """
    citations: dict[str, list[Citation]] = {}
    tests = repo / "tests"
    for path in sorted(tests.rglob("*.py")) if tests.is_dir() else []:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        rel = path.relative_to(repo).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            for decorator in node.decorator_list:
                for cited in _intent_ids(decorator):
                    citations.setdefault(cited, []).append(
                        Citation(id=cited, file=rel, line=decorator.lineno, test=node.name)
                    )
    return citations


def _intent_ids(node: ast.expr) -> list[str]:
    if not isinstance(node, ast.Call):
        return []
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "intent"):
        return []
    return [
        arg.value
        for arg in node.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]
