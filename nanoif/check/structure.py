"""``nanoif check structure``: deterministic checks over ``src/``.

Errors (the command exits 1): broken links, duplicate passage names, a
missing or invalid ``StoryData``, unreadable files, and syntax errors in
``story-overrides.txt``.
Warnings: orphan passages (unreachable from the start passage), file names
that match neither ``<INITIALS>-<YYYYMMDD>.twee`` nor an infrastructure file,
prose files without a ``:: Day <N> <INITIALS>`` passage, unknown
``storyStyle`` keys.
Info: reachable passages with no outgoing links that are not tagged
``ending``.
"""

from __future__ import annotations

import json
import re
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from nanoif.check.overrides import parse_overrides
from nanoif.schemas.artifacts import validate_artifact
from nanoif.twee.files import TweePassage, find_twee_files, split_twee
from nanoif.twee.links import find_links

Level = Literal["error", "warning", "info"]

INFRA_FILES = frozenset({"Start", "StoryData", "StoryTitle", "StoryStyles", "PathIdDisplay"})
GENERATED_FILES = frozenset({"PathIdLookup"})
PROSE_FILE_RE = re.compile(r"^(?P<initials>[A-Za-z]{1,10})-(?P<date>\d{8})$")
METADATA_PASSAGES = frozenset({"StoryData", "StoryTitle"})
CODE_TAGS = frozenset({"script", "stylesheet"})
NOT_IN_FLOW_TAGS = CODE_TAGS | {"footer", "header", "startup"}
ENDING_TAG = "ending"
IFID_RE = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$", re.I)
STORY_STYLE_VALUES = {
    "perspective": frozenset({"first-person", "second-person", "third-person"}),
    "tense": frozenset({"past", "present", "future"}),
}
_SEVERITY = {"error": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class Finding:
    """One result of the structure check.

    Attributes:
        level: ``error``, ``warning`` or ``info``.
        code: Stable identifier, for example ``broken-link``.
        file: Repository-relative POSIX path, or None when not tied to a file.
        line: 1-based line, or None.
        passage: Passage name, or None.
        message: What is wrong, for a writer.
    """

    level: Level
    code: str
    file: str | None
    line: int | None
    passage: str | None
    message: str


@dataclass(frozen=True)
class _Declared:
    passage: TweePassage
    file: str


def _load(src_dir: Path, root: Path, findings: list[Finding]) -> list[_Declared]:
    declared: list[_Declared] = []
    for path in find_twee_files(src_dir):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(Finding("error", "unreadable-file", rel, None, None, str(exc)))
            continue
        declared.extend(_Declared(passage, rel) for passage in split_twee(text))
    return declared


def _check_duplicates(declared: list[_Declared], findings: list[Finding]) -> dict[str, _Declared]:
    first: dict[str, _Declared] = {}
    for entry in declared:
        name = entry.passage.name
        if name in first:
            original = first[name]
            findings.append(
                Finding(
                    "error",
                    "duplicate-passage",
                    entry.file,
                    entry.passage.line,
                    name,
                    f"passage {name!r} is also declared at "
                    f"{original.file}:{original.passage.line}",
                )
            )
        else:
            first[name] = entry
    return first


def _story_data_finding(entry: _Declared, level: Level, code: str, message: str) -> Finding:
    return Finding(level, code, entry.file, entry.passage.line, "StoryData", message)


def _check_story_style(
    entry: _Declared,
    style: object,
    invalid: Callable[[str], None],
    findings: list[Finding],
) -> None:
    if not isinstance(style, dict):
        invalid("storyStyle must be a JSON object")
        return
    for key, allowed in STORY_STYLE_VALUES.items():
        if key in style and style[key] not in allowed:
            invalid(f"storyStyle.{key} must be one of {sorted(allowed)}, got {style[key]!r}")
    if "protagonist" in style:
        protagonist = style["protagonist"]
        if not isinstance(protagonist, str) or not protagonist.strip():
            invalid("storyStyle.protagonist must be a non-empty string")
    for key in sorted(set(style) - set(STORY_STYLE_VALUES) - {"protagonist"}):
        message = f"storyStyle.{key} is not a known setting and will be ignored"
        findings.append(_story_data_finding(entry, "warning", "story-style-unknown-key", message))


def _check_story_data(passages: dict[str, _Declared], findings: list[Finding]) -> str | None:
    """Validate StoryData; return the start passage name when it is usable."""
    entry = passages.get("StoryData")
    if entry is None:
        findings.append(
            Finding("error", "story-data-missing", None, None, None, "no StoryData passage")
        )
        return "Start" if "Start" in passages else None

    def invalid(message: str) -> None:
        findings.append(_story_data_finding(entry, "error", "story-data-invalid", message))

    try:
        data = json.loads(entry.passage.text)
    except json.JSONDecodeError as exc:
        invalid(f"StoryData is not valid JSON: {exc.msg} (line {exc.lineno})")
        return None
    if not isinstance(data, dict):
        invalid("StoryData must be a JSON object")
        return None
    ifid = data.get("ifid")
    if not isinstance(ifid, str) or not IFID_RE.match(ifid):
        invalid(f"ifid must be a UUID like 0683974A-9DD8-4A14-BC84-C9519DDDA688, got {ifid!r}")
    start = data.get("start", "Start")
    if not isinstance(start, str) or start not in passages:
        invalid(f"start passage {start!r} does not exist")
        start = None
    style = data.get("storyStyle")
    if style is not None:
        _check_story_style(entry, style, invalid, findings)
    return start


def _in_flow(entry: _Declared) -> bool:
    return entry.passage.name not in METADATA_PASSAGES and NOT_IN_FLOW_TAGS.isdisjoint(
        entry.passage.tags
    )


def _check_links(
    passages: dict[str, _Declared], findings: list[Finding]
) -> dict[str, list[str]]:
    """Report broken links; return the adjacency of links that resolve."""
    graph: dict[str, list[str]] = {}
    for name, entry in passages.items():
        if name in METADATA_PASSAGES or not CODE_TAGS.isdisjoint(entry.passage.tags):
            continue
        targets: list[str] = []
        for link in find_links(entry.passage.text):
            if link.target in passages:
                if link.target not in targets:
                    targets.append(link.target)
                continue
            findings.append(
                Finding(
                    "error",
                    "broken-link",
                    entry.file,
                    entry.passage.body_line + entry.passage.text.count("\n", 0, link.start),
                    name,
                    f"{name!r} links to {link.target!r}, which does not exist",
                )
            )
        graph[name] = targets
    return graph


def _check_reachability(
    passages: dict[str, _Declared],
    graph: dict[str, list[str]],
    start: str | None,
    findings: list[Finding],
) -> None:
    if start is None:
        return
    reachable = {start}
    queue = deque([start])
    while queue:
        for target in graph.get(queue.popleft(), []):
            if target not in reachable:
                reachable.add(target)
                queue.append(target)
    for name, entry in passages.items():
        if not _in_flow(entry):
            continue
        if name not in reachable:
            findings.append(
                Finding(
                    "warning",
                    "orphan-passage",
                    entry.file,
                    entry.passage.line,
                    name,
                    f"{name!r} cannot be reached from the start passage {start!r}",
                )
            )
        elif not graph.get(name) and ENDING_TAG not in entry.passage.tags:
            findings.append(
                Finding(
                    "info",
                    "dead-end",
                    entry.file,
                    entry.passage.line,
                    name,
                    f"{name!r} has no links; tag it [{ENDING_TAG}] if it is meant to end the story",
                )
            )


def _check_naming(declared: list[_Declared], findings: list[Finding]) -> None:
    by_file: dict[str, list[TweePassage]] = {}
    for entry in declared:
        by_file.setdefault(entry.file, []).append(entry.passage)
    files = sorted({entry.file for entry in declared})
    for file in files:
        stem = Path(file).stem
        if stem in INFRA_FILES or stem in GENERATED_FILES:
            continue
        match = PROSE_FILE_RE.match(stem)
        valid_date = False
        if match is not None:
            try:
                datetime.strptime(match.group("date"), "%Y%m%d")
                valid_date = True
            except ValueError:
                valid_date = False
        if match is None or not valid_date:
            findings.append(
                Finding(
                    "warning",
                    "file-naming",
                    file,
                    None,
                    None,
                    f"{Path(file).name} should be named <INITIALS>-<YYYYMMDD>.twee "
                    "(for example AB-20261101.twee)",
                )
            )
            continue
        initials = match.group("initials")
        day_re = re.compile(rf"^Day \d+ {re.escape(initials)}$")
        if not any(day_re.match(passage.name) for passage in by_file.get(file, [])):
            findings.append(
                Finding(
                    "warning",
                    "missing-day-passage",
                    file,
                    1,
                    None,
                    f"{Path(file).name} has no ':: Day <N> {initials}' entry passage",
                )
            )


def _check_overrides(path: Path | None, root: Path, findings: list[Finding]) -> None:
    if path is None or not path.exists():
        return
    try:
        rel = path.resolve().relative_to(root).as_posix()
    except ValueError:
        rel = path.as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        findings.append(Finding("error", "overrides-syntax", rel, None, None, str(exc)))
        return
    for error in parse_overrides(text)[1]:
        findings.append(Finding("error", "overrides-syntax", rel, error.line, None, error.message))


def check_structure(
    src_dir: Path, overrides_path: Path | None = None, repo_root: Path | None = None
) -> list[Finding]:
    """Run every structure check.

    Args:
        src_dir: The story source directory.
        overrides_path: ``story-overrides.txt``; skipped when None or absent.
        repo_root: Root that reported file paths are relative to; defaults to
            the parent of ``src_dir``.

    Returns:
        Findings sorted by severity, then file and line.
    """
    root = (repo_root or src_dir.resolve().parent).resolve()
    findings: list[Finding] = []
    declared = _load(src_dir.resolve(), root, findings)
    passages = _check_duplicates(declared, findings)
    start = _check_story_data(passages, findings)
    graph = _check_links(passages, findings)
    _check_reachability(passages, graph, start, findings)
    _check_naming(declared, findings)
    _check_overrides(overrides_path, root, findings)
    return sorted(
        findings,
        key=lambda f: (_SEVERITY[f.level], f.file or "", f.line or 0, f.code, f.passage or ""),
    )


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def format_findings(findings: list[Finding], fmt: str) -> str:
    """Render findings.

    Args:
        findings: The result of :func:`check_structure`.
        fmt: ``text``, ``json`` or ``github`` (workflow annotations).

    Returns:
        The rendered findings; empty text output for no findings.

    Raises:
        ValueError: For an unknown format.
    """
    if fmt == "json":
        document = [asdict(finding) for finding in findings]
        validate_artifact(document, "structure_findings")
        return json.dumps(document, indent=2)
    lines = []
    for finding in findings:
        if fmt == "text":
            where = finding.file or "<story>"
            if finding.line is not None:
                where += f":{finding.line}"
            lines.append(f"{finding.level}: {where}: [{finding.code}] {finding.message}")
        elif fmt == "github":
            command = {"error": "error", "warning": "warning", "info": "notice"}[finding.level]
            props = [f"title={_escape_property(finding.code)}"]
            if finding.file:
                props.insert(0, f"file={_escape_property(finding.file)}")
                if finding.line is not None:
                    props.insert(1, f"line={finding.line}")
            lines.append(f"::{command} {','.join(props)}::{_escape_data(finding.message)}")
        else:
            raise ValueError(f"unknown format {fmt!r}")
    return "\n".join(lines)
