"""The passages the Story Bible reads: prose passages straight from ``src/``.

No build artifact and no Tweego: the files are split with the one passage-header parser
(:mod:`nanoif.twee.files`) and hashed with :func:`nanoif.twee.passages.content_hash`, so
the extractor, the page's Freshness section and canon retrieval agree on every hash.
Infrastructure passages (:func:`nanoif.twee.prose.is_infra`) are left out.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nanoif.errors import BibleError
from nanoif.twee.files import find_twee_files, split_twee
from nanoif.twee.passages import content_hash
from nanoif.twee.prose import is_infra


@dataclass(frozen=True)
class SourcePassage:
    """One prose passage as the Story Bible reads it.

    Attributes:
        name: Passage name.
        file: Repository-relative POSIX path of its ``.twee`` file.
        text: Passage body, stripped.
        content_hash: :func:`~nanoif.twee.passages.content_hash` of ``text``.
    """

    name: str
    file: str
    text: str
    content_hash: str


def bible_passages(repo: Path, src: Path | None = None) -> list[SourcePassage]:
    """Read every prose passage under ``src/``.

    A passage declared twice keeps its first declaration in sorted file order, as
    everywhere else; the structure check reports the duplicate.

    Args:
        repo: The repository root (file names are relative to it).
        src: The story source; defaults to ``<repo>/src``.

    Returns:
        Passages sorted by name.

    Raises:
        BibleError: The source directory does not exist, or a ``.twee`` file cannot be
            read as UTF-8 text (the structure check reports it too).
    """
    src = src or repo / "src"
    if not src.is_dir():
        raise BibleError(f"story source not found: {src}")
    root = repo.resolve()
    found: dict[str, SourcePassage] = {}
    for path in find_twee_files(src):
        file = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise BibleError(f"cannot read {file} as UTF-8 text: {exc}") from exc
        for passage in split_twee(text):
            if passage.name in found or is_infra(passage.name, passage.tags):
                continue
            found[passage.name] = SourcePassage(
                passage.name, file, passage.text, content_hash(passage.text)
            )
    return [found[name] for name in sorted(found)]


def current_hashes(passages: list[SourcePassage]) -> dict[str, str]:
    """Return passage name to content hash.

    Args:
        passages: From :func:`bible_passages`.

    Returns:
        The mapping.
    """
    return {passage.name: passage.content_hash for passage in passages}
