"""Twee source files: the one passage-header regex and passage-to-file mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PASSAGE_HEADER_RE = re.compile(
    r"^::[ \t]*(?P<name>[^\[\{\s:][^\[\{\r\n]*?)[ \t]*"
    r"(?:\[(?P<tags>[^\]\r\n]*)\])?[ \t]*"
    r"(?:\{(?P<meta>[^\r\n]*)\})?[ \t]*$",
    re.MULTILINE,
)
"""Matches a Twee 3 passage header ``:: Name [tags] {metadata}``.

The space after ``::`` is optional."""

PROSE_FILE_RE = re.compile(r"^(?P<initials>[A-Za-z]{1,10})-(?P<date>\d{8})$")
"""A writer's daily file stem, ``<INITIALS>-<YYYYMMDD>``."""

DAY_PASSAGE_RE = re.compile(r"^Day (?P<day>\d+) (?P<initials>[A-Za-z]{1,10})$")
"""A daily entry passage name, ``Day <N> <INITIALS>``."""


@dataclass(frozen=True)
class ProseFileName:
    """What a prose file's name says.

    Attributes:
        initials: The writer's initials.
        date: The day, as ``YYYY-MM-DD``.
    """

    initials: str
    date: str


def parse_prose_file_name(file_name: str) -> ProseFileName | None:
    """Parse ``<INITIALS>-<YYYYMMDD>.twee``.

    Args:
        file_name: A file name, with or without the ``.twee`` suffix.

    Returns:
        The initials and date, or None when the name does not follow the
        convention or the date does not exist.
    """
    match = PROSE_FILE_RE.match(Path(file_name).stem)
    if match is None:
        return None
    try:
        day = datetime.strptime(match.group("date"), "%Y%m%d")
    except ValueError:
        return None
    return ProseFileName(match.group("initials"), day.strftime("%Y-%m-%d"))


@dataclass(frozen=True)
class TweePassage:
    """One passage as it appears in a Twee source file.

    Attributes:
        name: Passage name.
        tags: Tags from the header, in order.
        text: Passage body with surrounding whitespace stripped.
        line: 1-based line of the header in the file.
        body_line: 1-based line where ``text`` starts (the header line when empty).
    """

    name: str
    tags: tuple[str, ...]
    text: str
    line: int
    body_line: int


@dataclass(frozen=True)
class PassageLocation:
    """Where a passage is declared.

    Attributes:
        name: Passage name.
        file: Absolute path of the ``.twee`` file.
        line: 1-based line of the header.
        tags: Tags from the header.
    """

    name: str
    file: Path
    line: int
    tags: tuple[str, ...]


def split_twee(text: str) -> list[TweePassage]:
    """Split Twee source into passages.

    Args:
        text: Contents of one ``.twee`` file.

    Returns:
        Passages in file order. Text before the first header is ignored.
    """
    text = text.replace("\r\n", "\n")
    headers = list(PASSAGE_HEADER_RE.finditer(text))
    passages: list[TweePassage] = []
    for index, match in enumerate(headers):
        body_start = match.end()
        body_end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        tags = tuple((match.group("tags") or "").split())
        raw_body = text[body_start:body_end]
        body = raw_body.strip()
        line = text.count("\n", 0, match.start()) + 1
        leading = raw_body[: len(raw_body) - len(raw_body.lstrip())]
        passages.append(
            TweePassage(
                name=match.group("name").strip(),
                tags=tags,
                text=body,
                line=line,
                body_line=line + leading.count("\n") if body else line,
            )
        )
    return passages


def find_twee_files(src_dir: Path) -> list[Path]:
    """Return every ``.twee`` file under ``src_dir``, recursively, in sorted order.

    Args:
        src_dir: Directory holding the story source.

    Returns:
        Absolute paths, sorted so that the result is deterministic.
    """
    return sorted(path.resolve() for path in src_dir.rglob("*.twee") if path.is_file())


def passage_locations(src_dir: Path) -> dict[str, PassageLocation]:
    """Map passage names to the file and line where they are declared.

    When a name is declared more than once the first declaration in sorted file
    order wins; the structure check reports duplicates separately.

    Args:
        src_dir: Directory holding the story source.

    Returns:
        Passage name to its location.
    """
    locations: dict[str, PassageLocation] = {}
    for file in find_twee_files(src_dir):
        for passage in split_twee(file.read_text(encoding="utf-8")):
            locations.setdefault(
                passage.name,
                PassageLocation(passage.name, file, passage.line, passage.tags),
            )
    return locations


def relative_file(location: PassageLocation, repo_root: Path) -> str:
    """Return a location's file as a POSIX path relative to the repository root.

    Args:
        location: A passage location.
        repo_root: The repository root the path should be relative to.

    Returns:
        For example ``src/AB-20251101.twee``.
    """
    return location.file.relative_to(repo_root.resolve()).as_posix()
