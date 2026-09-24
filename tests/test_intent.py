"""The intent gate: acceptance criteria and ADRs are traceable, and code changes carry intent."""

from __future__ import annotations

from pathlib import Path

import pytest

from nanoif.cli import main
from nanoif.intent import (
    check_commit,
    check_repo,
    classify_paths,
    load_index,
    scan_citations,
)
from tests.conftest import commit_all, git

FEATURE = """# Structure check

## Acceptance criteria

- AC-structure-check-1: A link to a missing passage is reported with file and line.
- AC-structure-check-2: Duplicate passage names are reported. (verify: test)
- AC-structure-check-3: The Structure check run appears on every PR. (verify: workflow)
"""

ADR_1 = "# ADR-001: Old thing\n\nStatus: Superseded by ADR-002\n"
ADR_2 = "# ADR-002: New thing\n\nStatus: Accepted\n"

TEST_OK = '''import pytest


@pytest.mark.intent("AC-structure-check-1", "AC-structure-check-2")
def test_one():
    pass
'''


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def intent_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    _write(repo, "features/structure-check.md", FEATURE)
    _write(repo, "architecture/001-old-thing.md", ADR_1)
    _write(repo, "architecture/002-new-thing.md", ADR_2)
    _write(repo, "tests/test_structure.py", TEST_OK)
    _write(repo, "nanoif/thing.py", "X = 1\n")
    commit_all(repo, "base", "2026-09-01T10:00:00+00:00")
    return repo


def codes(findings):
    return sorted(f.code for f in findings)


# -- index -------------------------------------------------------------------------


def test_index_parses_criteria_with_verify_and_line_numbers(intent_repo):
    index = load_index(intent_repo)
    first = index.criteria["AC-structure-check-1"]
    assert first.file == "features/structure-check.md"
    assert first.line == 5
    assert first.verify == "test"
    assert index.criteria["AC-structure-check-3"].verify == "workflow"
    assert index.adrs["ADR-001"].superseded_by == "ADR-002"
    assert index.adrs["ADR-002"].status == "Accepted"


def test_citations_are_read_from_intent_markers(intent_repo):
    citations = scan_citations(intent_repo)
    assert sorted(citations) == ["AC-structure-check-1", "AC-structure-check-2"]
    assert citations["AC-structure-check-1"][0].file == "tests/test_structure.py"


# -- check -------------------------------------------------------------------------


def test_clean_repo_has_no_errors(intent_repo):
    assert [f for f in check_repo(intent_repo) if f.level == "error"] == []


def test_test_criterion_without_a_citing_test_is_an_error(intent_repo):
    _write(intent_repo, "tests/test_structure.py", TEST_OK.replace(', "AC-structure-check-2"', ""))
    assert "untested-criterion" in codes(check_repo(intent_repo))


def test_citation_of_unknown_criterion_is_an_error(intent_repo):
    _write(intent_repo, "tests/test_other.py", TEST_OK.replace("check-1", "check-99"))
    assert "unknown-citation" in codes(check_repo(intent_repo))


def test_criterion_id_must_match_its_file_stem(intent_repo):
    _write(intent_repo, "features/other.md", "- AC-structure-check-7: wrong file\n")
    assert "criterion-prefix" in codes(check_repo(intent_repo))


def test_duplicate_criterion_ids_are_an_error(intent_repo):
    _write(
        intent_repo,
        "features/structure-check.md",
        FEATURE + "- AC-structure-check-1: again\n",
    )
    assert "duplicate-criterion" in codes(check_repo(intent_repo))


def test_feature_note_without_criteria_is_an_error(intent_repo):
    _write(intent_repo, "features/empty.md", "# Nothing testable here\n")
    assert "no-criteria" in codes(check_repo(intent_repo))


def test_adr_superseded_by_a_missing_adr_is_an_error(intent_repo):
    _write(intent_repo, "architecture/003-x.md", "# ADR-003: X\n\nStatus: Superseded by ADR-009\n")
    assert "dangling-supersede" in codes(check_repo(intent_repo))


def test_adr_without_status_is_an_error(intent_repo):
    _write(intent_repo, "architecture/004-y.md", "# ADR-004: Y\n\nNo status here.\n")
    assert "adr-status" in codes(check_repo(intent_repo))


# -- commit gate -------------------------------------------------------------------


def test_path_classification():
    governed, intent = classify_paths(
        [
            "nanoif/a.py",
            ".github/workflows/x.yml",
            "src/StoryData.twee",
            "src/AB-20261101.twee",
            "tests/test_a.py",
            "features/a.md",
            "PRIORITIES.md",
            "README.md",
        ]
    )
    assert governed == ["nanoif/a.py", ".github/workflows/x.yml", "src/StoryData.twee"]
    assert intent == ["features/a.md", "PRIORITIES.md"]


def test_code_change_without_intent_or_trailer_is_rejected():
    result = check_commit("fix: tweak parser\n", ["nanoif/a.py"])
    assert not result.ok
    assert "Intent: unchanged" in result.message


def test_code_change_with_intent_doc_passes():
    assert check_commit("feat: x\n", ["nanoif/a.py", "features/a.md"]).ok


def test_code_change_with_unchanged_trailer_and_reason_passes():
    msg = "fix: x\n\nbody\n\nIntent: unchanged (pure refactor, same outputs)\n"
    assert check_commit(msg, ["nanoif/a.py"]).ok


def test_trailer_without_reason_is_rejected():
    assert not check_commit("fix: x\n\nIntent: unchanged\n", ["nanoif/a.py"]).ok
    assert not check_commit("fix: x\n\nIntent: unchanged ()\n", ["nanoif/a.py"]).ok


def test_ungoverned_changes_need_nothing():
    assert check_commit("test: more tests\n", ["tests/test_a.py", "README.md"]).ok
    assert check_commit("chore: prose\n", ["src/AB-20261101.twee"]).ok


def test_cli_commit_msg_uses_staged_files(intent_repo, capsys):
    _write(intent_repo, "nanoif/thing.py", "X = 2\n")
    git(intent_repo, "add", "-A")
    msg = intent_repo / "MSG"
    msg.write_text("fix: bump\n", encoding="utf-8")
    assert main(["intent", "commit-msg", str(msg), "--repo", str(intent_repo)]) == 1
    assert "Intent: unchanged" in capsys.readouterr().err
    msg.write_text("fix: bump\n\nIntent: unchanged (constant only)\n", encoding="utf-8")
    assert main(["intent", "commit-msg", str(msg), "--repo", str(intent_repo)]) == 0


def test_cli_range_checks_each_non_merge_commit(intent_repo, capsys):
    base = git(intent_repo, "rev-parse", "HEAD").strip()
    _write(intent_repo, "nanoif/thing.py", "X = 3\n")
    commit_all(intent_repo, "fix: good\n\nIntent: unchanged (value only)", "2026-09-02T10:00:00+00:00")
    assert main(["intent", "range", "--repo", str(intent_repo), "--base", base]) == 0
    _write(intent_repo, "nanoif/thing.py", "X = 4\n")
    bad = commit_all(intent_repo, "fix: bad", "2026-09-03T10:00:00+00:00")
    assert main(["intent", "range", "--repo", str(intent_repo), "--base", base]) == 1
    assert bad[:7] in capsys.readouterr().err


def test_cli_check_exit_codes(intent_repo, capsys):
    assert main(["intent", "check", "--repo", str(intent_repo)]) == 0
    _write(intent_repo, "tests/test_other.py", TEST_OK.replace("check-1", "check-99"))
    assert main(["intent", "check", "--repo", str(intent_repo)]) == 1
    assert "unknown-citation" in capsys.readouterr().out
