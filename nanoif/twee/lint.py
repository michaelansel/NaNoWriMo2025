"""Twee formatting rules.

``nanoif lint`` only reports. :func:`fix_file` exists for tests and local use
and is deliberately not reachable from the CLI: automation never rewrites a
writer's prose.

Rules:

1. ``passage-header-spacing``: a space after ``::`` in passage headers.
2. ``blank-line-after-header``: a blank line after a passage header, except
   for special passages (see :data:`SPECIAL_PASSAGE_NAMES`, :data:`SPECIAL_PASSAGE_TAGS`).
3. ``blank-line-between-passages``: exactly one blank line before a header.
4. ``trailing-whitespace``: no whitespace at the end of a line.
5. ``final-newline``: the file ends with exactly one newline.
6. ``single-blank-lines``: no runs of blank lines.
7. ``link-block-spacing``: a blank line before and after a block of
   one-link-per-line choices, and none between the links.

The 2025 ``smart-quotes`` rule is gone: curly quotes are the writer's choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nanoif.errors import LintError
from nanoif.twee.files import PASSAGE_HEADER_RE

SPECIAL_PASSAGE_NAMES = frozenset(
    {"StoryData", "StoryTitle", "StoryStylesheet", "StoryBanner", "StoryMenu", "StoryInit"}
)
SPECIAL_PASSAGE_TAGS = frozenset({"stylesheet", "script"})


@dataclass(frozen=True)
class Violation:
    """One formatting issue.

    Attributes:
        file: The file, as given to the linter.
        line: 1-based line number.
        rule: Rule name, for example ``trailing-whitespace``.
        message: What is wrong.
    """

    file: Path
    line: int
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: [{self.rule}] {self.message}"

    def github(self) -> str:
        """Render as a GitHub Actions warning annotation.

        Returns:
            One ``::warning`` workflow command.
        """
        return f"::warning file={self.file},line={self.line},title={self.rule}::{self.message}"


def parse_passage_header(line: str) -> tuple[str, list[str]] | None:
    """Parse a passage header with the one header regex.

    Args:
        line: One line of Twee source, without its line ending.

    Returns:
        ``(name, tags)`` for a header, None otherwise.
    """
    match = PASSAGE_HEADER_RE.match(line)
    if match is None:
        return None
    return match.group("name").strip(), (match.group("tags") or "").split()


def is_special_passage(name: str, tags: list[str]) -> bool:
    """Return whether a passage is exempt from ``blank-line-after-header``.

    Args:
        name: Passage name.
        tags: Passage tags.

    Returns:
        True for Twine special passages and ``stylesheet``/``script`` passages.
    """
    return name in SPECIAL_PASSAGE_NAMES or not SPECIAL_PASSAGE_TAGS.isdisjoint(tags)


def is_block_link(line: str) -> bool:
    """Return whether a line holds exactly one ``[[link]]`` and nothing else.

    Args:
        line: One line of Twee source.

    Returns:
        True for a block link.
    """
    stripped = line.strip()
    return (
        stripped.startswith("[[")
        and stripped.endswith("]]")
        and len(stripped) > 4
        and stripped.count("[[") == 1
        and stripped.count("]]") == 1
    )


def _blank(line: str) -> bool:
    return line.strip() == ""


def _run(text: str, file: Path, fix: bool) -> tuple[list[Violation], list[str]]:
    """Apply every rule; return the violations and the fixed lines."""
    lines = text.splitlines(keepends=True)
    violations: list[Violation] = []
    out: list[str] = []
    if not lines:
        return violations, out

    def report(line: int, rule: str, message: str) -> None:
        violations.append(Violation(file, line, rule, message))

    last_was_header = False
    last_header: tuple[str, list[str]] | None = None
    in_link_block = False
    last_non_blank_was_narrative = False

    for index, raw in enumerate(lines):
        number = index + 1
        line = raw.rstrip("\n\r")

        if line and line != line.rstrip():
            report(number, "trailing-whitespace", "Line has trailing whitespace")
            if fix:
                line = line.rstrip()

        header = parse_passage_header(line)
        if is_block_link(line):
            if not in_link_block:
                if last_non_blank_was_narrative and out and not _blank(out[-1]):
                    report(number, "link-block-spacing", "Missing blank line before link block")
                    if fix:
                        out.append("")
                in_link_block = True
            elif out and _blank(out[-1]):
                report(
                    number,
                    "link-block-spacing",
                    "Blank line between block links (should be removed)",
                )
                if fix:
                    out.pop()
            last_non_blank_was_narrative = False
        elif not _blank(line):
            if in_link_block and header is None and out and not _blank(out[-1]):
                report(number, "link-block-spacing", "Missing blank line after link block")
                if fix:
                    out.append("")
            in_link_block = False
            if header is None:
                last_non_blank_was_narrative = True
        else:
            last_non_blank_was_narrative = False

        if header is not None:
            if not line.startswith(":: "):
                report(number, "passage-header-spacing", "Missing space after :: in passage header")
                if fix:
                    line = ":: " + line[2:].lstrip()
            if out:
                blanks = 0
                for previous in reversed(out):
                    if not _blank(previous):
                        break
                    blanks += 1
                if blanks != 1:
                    report(
                        number,
                        "blank-line-between-passages",
                        f"Expected exactly 1 blank line before passage header, found {blanks}",
                    )
                    if fix:
                        while blanks > 1 and out and _blank(out[-1]):
                            out.pop()
                            blanks -= 1
                        if blanks == 0:
                            out.append("")
            last_was_header = True
            last_header = header
            in_link_block = False
            last_non_blank_was_narrative = False
        else:
            if last_was_header and not _blank(line) and last_header is not None:
                if not is_special_passage(*last_header):
                    message = "Missing blank line after passage header"
                    report(number - 1, "blank-line-after-header", message)
                    if fix:
                        out.append("")
            last_was_header = False

        if _blank(line) and out and _blank(out[-1]):
            report(number, "single-blank-lines", "Multiple consecutive blank lines")
            if fix:
                continue

        out.append(line)

    trailing = 0
    for previous in reversed(out):
        if not _blank(previous):
            break
        trailing += 1
    if trailing:
        report(
            len(lines),
            "final-newline",
            f"File has {trailing} trailing blank line(s), expected 0",
        )
    if fix:
        while out and _blank(out[-1]):
            out.pop()
    if not lines[-1].endswith(("\n", "\r")):
        report(len(lines), "final-newline", "File does not end with newline")
    return violations, out


def lint_text(text: str, file: Path) -> list[Violation]:
    """Check Twee source.

    Args:
        text: File contents.
        file: The file name to put in each violation.

    Returns:
        Violations in line order of detection; empty for a well-formatted file.
    """
    return _run(text, file, fix=False)[0]


def fix_text(text: str, file: Path) -> tuple[str, list[Violation]]:
    """Fix Twee source.

    Args:
        text: File contents.
        file: The file name to put in each violation.

    Returns:
        The fixed text (the input unchanged when there was nothing to fix) and
        the violations that were fixed.
    """
    violations, out = _run(text, file, fix=True)
    if not violations:
        return text, []
    fixed = "\n".join(out)
    return (fixed + "\n" if fixed else fixed), violations


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LintError(f"cannot read {path}: {exc}") from exc


def lint_file(path: Path) -> list[Violation]:
    """Check one ``.twee`` file.

    Args:
        path: The file.

    Returns:
        Its violations.

    Raises:
        LintError: If the file cannot be read as UTF-8.
    """
    return lint_text(_read(path), path)


def fix_file(path: Path) -> list[Violation]:
    """Rewrite one ``.twee`` file with every violation fixed. Not exposed on the CLI.

    Args:
        path: The file.

    Returns:
        The violations that were fixed; empty when the file was left untouched.

    Raises:
        LintError: If the file cannot be read as UTF-8.
    """
    fixed, violations = fix_text(_read(path), path)
    if violations:
        path.write_text(fixed, encoding="utf-8")
    return violations


def lint_path(path: Path) -> list[Violation]:
    """Check a ``.twee`` file, or every ``.twee`` file under a directory.

    Args:
        path: A file or directory.

    Returns:
        All violations, files in sorted order.

    Raises:
        LintError: If the path does not exist, is not a ``.twee`` file, or a
            file cannot be read.
    """
    if path.is_dir():
        return [v for file in sorted(path.rglob("*.twee")) for v in lint_file(file)]
    if not path.exists():
        raise LintError(f"{path} does not exist")
    if path.suffix != ".twee":
        raise LintError(f"{path} is not a .twee file")
    return lint_file(path)
