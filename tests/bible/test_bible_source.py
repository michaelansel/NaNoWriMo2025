"""What the Story Bible reads: prose passages from src/, with the nanoif.twee hash."""

from __future__ import annotations

from pathlib import Path

import pytest

from nanoif.bible.source import SourcePassage, bible_passages
from nanoif.twee.passages import content_hash

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eval-story"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.intent("ADR-020")
def test_reads_prose_passages_and_skips_infrastructure(tmp_path):
    write(tmp_path / "src" / "StoryData.twee", ':: StoryData\n{"start": "Start"}\n')
    write(tmp_path / "src" / "StoryTitle.twee", ":: StoryTitle\nThe Lantern Crossing\n")
    write(
        tmp_path / "src" / "StoryStyles.twee",
        ":: StoryStylesheet [stylesheet]\nbody {}\n\n:: Footer [footer]\nfoot\n",
    )
    write(tmp_path / "src" / "Start.twee", ":: Start\n\nThe river town. [[Day 1 EV]]\n")
    write(
        tmp_path / "src" / "EV-20261101.twee",
        ":: Day 1 EV\n\nWren woke.\n\n:: Start\n\nThis Start is declared first in sorted file order.\n",
    )
    passages = bible_passages(tmp_path)
    assert [p.name for p in passages] == ["Day 1 EV", "Start"]
    day1 = passages[0]
    assert day1 == SourcePassage(
        "Day 1 EV", "src/EV-20261101.twee", "Wren woke.", content_hash("Wren woke.")
    )
    assert passages[1].file == "src/EV-20261101.twee"
    assert passages[1].text == "This Start is declared first in sorted file order."


def test_reads_the_eval_story():
    names = {p.name for p in bible_passages(FIXTURE)}
    assert "The widow's door" in names and "Day 4 EV" in names
    assert not names & {"StoryData", "StoryTitle"}


def test_missing_src_is_an_error(tmp_path):
    from nanoif.errors import BibleError

    with pytest.raises(BibleError, match="src"):
        bible_passages(tmp_path)


def test_a_file_that_is_not_utf8_is_a_typed_error(tmp_path):
    from nanoif.errors import BibleError

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "EV-20261101.twee").write_bytes(b":: Day 1 EV\n\n\xff\xfe\n")
    with pytest.raises(BibleError, match="EV-20261101.twee"):
        bible_passages(tmp_path)
