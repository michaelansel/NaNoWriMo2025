"""Tests for ``nanoif.git.service`` against a throwaway repository."""

import pytest

from nanoif.errors import GitError
from nanoif.git.service import FileDates, GitService
from tests.conftest import commit_all, git


def test_rev_parse_resolves_head_and_caches(story_repo):
    service = GitService(story_repo)
    sha = service.rev_parse("HEAD")
    assert sha == git(story_repo, "rev-parse", "HEAD").strip()
    assert service.rev_parse("HEAD") is sha


def test_rev_parse_unknown_ref_is_an_error(story_repo):
    service = GitService(story_repo)
    with pytest.raises(GitError, match="rev-parse"):
        service.rev_parse("no-such-ref-12345")
    assert service.ref_exists("HEAD") and not service.ref_exists("no-such-ref-12345")


def test_not_a_repository_is_an_error(tmp_path):
    with pytest.raises(GitError):
        GitService(tmp_path).rev_parse("HEAD")


def test_file_dates_created_and_modified_from_one_log(story_repo):
    (story_repo / "src" / "AB-20251101.twee").write_text(
        ":: Start\nMorning, again. [[Go left->Left]] or [[Go right->Right]]\n\n"
        ":: Left\nYou went left. [[End1]]\n\n:: Right\nYou went right. [[End2]]\n",
        encoding="utf-8",
    )
    commit_all(story_repo, "edit day one", "2025-11-03T10:00:00+00:00")
    (story_repo / "src" / "AB-20251104.twee").write_text(":: Loose\nUncommitted.\n", encoding="utf-8")
    dates = GitService(story_repo).file_dates("src")
    assert dates["src/AB-20251101.twee"] == FileDates(
        created="2025-11-01T10:00:00+00:00", modified="2025-11-03T10:00:00+00:00"
    )
    assert dates["src/AB-20251102.twee"] == FileDates(
        created="2025-11-02T10:00:00+00:00", modified="2025-11-02T10:00:00+00:00"
    )
    assert "src/AB-20251104.twee" not in dates


def test_file_dates_only_covers_the_directory(story_repo):
    (story_repo / "README.md").write_text("hi", encoding="utf-8")
    commit_all(story_repo, "readme", "2025-11-05T10:00:00+00:00")
    assert "README.md" not in GitService(story_repo).file_dates("src")


def test_list_files_at_ref(story_repo):
    service = GitService(story_repo)
    first = git(story_repo, "rev-list", "--max-parents=0", "HEAD").strip()
    assert service.list_files("HEAD", "src") == [
        "src/AB-20251101.twee",
        "src/AB-20251102.twee",
        "src/StoryData.twee",
        "src/StoryTitle.twee",
    ]
    assert service.list_files(first, "src") == [
        "src/AB-20251101.twee",
        "src/StoryData.twee",
        "src/StoryTitle.twee",
    ]
    assert service.list_files("HEAD", "nowhere") == []


def test_read_files_returns_contents_at_ref(story_repo):
    service = GitService(story_repo)
    first = git(story_repo, "rev-list", "--max-parents=0", "HEAD").strip()
    (story_repo / "src" / "AB-20251102.twee").write_text(":: End1\nChanged on disk.\n", encoding="utf-8")
    contents = service.read_files("HEAD", ["src/AB-20251102.twee", "src/StoryTitle.twee"])
    assert contents["src/AB-20251102.twee"].startswith(":: End1\nLeft ending.")
    assert contents["src/StoryTitle.twee"] == ":: StoryTitle\nTest Story\n"
    with pytest.raises(GitError, match="not a file"):
        service.read_files(first, ["src/AB-20251102.twee"])
    assert service.read_files("HEAD", []) == {}


def test_read_files_handles_unicode_sizes(story_repo):
    (story_repo / "src" / "AB-20251103.twee").write_text(":: Café\nDéjà vu → “quotes”\n", encoding="utf-8")
    commit_all(story_repo, "unicode", "2025-11-03T10:00:00+00:00")
    contents = GitService(story_repo).read_files("HEAD", ["src/AB-20251103.twee", "src/StoryTitle.twee"])
    assert contents["src/AB-20251103.twee"] == ":: Café\nDéjà vu → “quotes”\n"
    assert contents["src/StoryTitle.twee"] == ":: StoryTitle\nTest Story\n"


def test_snapshot_repository_commits_on_an_empty_base(tmp_path):
    from nanoif.git.service import snapshot_repository

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Start.twee").write_text(":: Start\nHello.\n", encoding="utf-8")
    base, head = snapshot_repository(tmp_path, "story")
    service = GitService(tmp_path)
    assert service.list_files(base, "src") == []
    assert service.list_files(head, "src") == ["src/Start.twee"]
    with pytest.raises(GitError, match="already a git repository"):
        snapshot_repository(tmp_path, "again")
