"""Twee source files: the one passage-header regex and passage-to-file mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PASSAGE_HEADER_RE = re.compile(
    r"^::[ \t]*(?P<name>[^\[\{\s:][^\[\{\r\n]*?)[ \t]*"
    r"(?:\[(?P<tags>[^\]\r\n]*)\])?[ \t]*"
    r"(?:\{(?P<meta>[^\r\n]*)\})?[ \t]*$",
    re.MULTILINE,
)
"""Matches a Twee 3 passage header ``:: Name [tags] {metadata}``.

The space after ``::`` is optional."""


@dataclass(frozen=True)
class TweePassage:
    """One passage as it appears in a Twee source file.

    Attributes:
        name: Passage name.
        tags: Tags from the header, in order.
        text: Passage body with surrounding whitespace stripped.
        line: 1-based line of the header in the file.
    """

    name: str
    tags: tuple[str, ...]
    text: str
    line: int


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
        passages.append(
            TweePassage(
                name=match.group("name").strip(),
                tags=tags,
                text=text[body_start:body_end].strip(),
                line=text.count("\n", 0, match.start()) + 1,
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
