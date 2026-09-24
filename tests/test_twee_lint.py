"""Tests for ``nanoif.twee.lint`` (ported from the 2025 scripts/test_lint_twee.py).

Each rule is tested in check mode (``lint_file``), fix mode (``fix_file``),
and for idempotency. The 2025 smart-quotes rule is gone; one test proves
curly quotes are no longer reported.
"""

from pathlib import Path

import pytest

from nanoif.cli import main
from nanoif.errors import LintError
from nanoif.twee.lint import (
    Violation,
    fix_file,
    fix_text,
    is_block_link,
    is_special_passage,
    lint_file,
    lint_path,
    parse_passage_header,
)


def lint(path, fix=False):
    """Check or fix a file; return (violations as text, whether the file was rewritten)."""
    if fix:
        fixed = fix_file(path)
        return [str(v) for v in fixed], bool(fixed)
    return [str(v) for v in lint_file(path)], False


class TestIsBlockLink:
    """Tests for is_block_link() function."""

    def test_simple_block_link(self):
        """Test simple block link."""
        assert is_block_link("[[Continue]]") is True

    def test_block_link_with_arrow(self):
        """Test block link with arrow syntax."""
        assert is_block_link("[[Continue->Next]]") is True

    def test_block_link_with_whitespace(self):
        """Test block link with leading/trailing whitespace."""
        assert is_block_link("  [[Continue]]  ") is True
        assert is_block_link("\t[[Continue]]\t") is True

    def test_inline_link_text_before(self):
        """Test that inline link with text before is not a block link."""
        assert is_block_link("Text before [[link]]") is False

    def test_inline_link_text_after(self):
        """Test that inline link with text after is not a block link."""
        assert is_block_link("[[link]] text after") is False

    def test_multiple_links(self):
        """Test that multiple links on same line is not a block link."""
        assert is_block_link("[[link1]] [[link2]]") is False

    def test_empty_brackets(self):
        """Test that empty brackets are not a block link."""
        assert is_block_link("[]") is False
        assert is_block_link("[[]]") is False

    def test_empty_line(self):
        """Test that empty line is not a block link."""
        assert is_block_link("") is False
        assert is_block_link("   ") is False

    def test_malformed_brackets(self):
        """Test that malformed brackets are not block links."""
        assert is_block_link("[Continue]") is False
        assert is_block_link("[[Continue]") is False
        assert is_block_link("[Continue]]") is False


class TestParsePassageHeader:
    """Tests for parse_passage_header() function."""

    def test_simple_header(self):
        """Test simple passage header."""
        result = parse_passage_header(":: Start")
        assert result == ('Start', [])

    def test_header_with_tags(self):
        """Test passage header with tags."""
        result = parse_passage_header(":: StoryStylesheet [stylesheet]")
        assert result == ('StoryStylesheet', ['stylesheet'])

    def test_header_multiple_tags(self):
        """Test passage header with multiple tags."""
        result = parse_passage_header(":: Passage [tag1 tag2]")
        assert result == ('Passage', ['tag1', 'tag2'])

    def test_header_no_space(self):
        """Test passage header without space after ::"""
        result = parse_passage_header("::NoSpace")
        assert result == ('NoSpace', [])

    def test_not_header(self):
        """Test line that is not a header."""
        result = parse_passage_header("Not a header")
        assert result is None


class TestIsSpecialPassage:
    """Tests for is_special_passage() function."""

    def test_special_by_name(self):
        """Test passages that are special by name."""
        assert is_special_passage('StoryData', []) is True
        assert is_special_passage('StoryTitle', []) is True
        assert is_special_passage('StoryStylesheet', []) is True

    def test_special_by_tag(self):
        """Test passages that are special by tag."""
        assert is_special_passage('MyStyles', ['stylesheet']) is True
        assert is_special_passage('MyScript', ['script']) is True

    def test_not_special(self):
        """Test passages that are not special."""
        assert is_special_passage('Start', []) is False
        assert is_special_passage('Regular Passage', ['tag']) is False


class TestPassageHeaderSpacing:
    """Tests for passage-header-spacing rule."""

    def test_detect_missing_space(self, tmp_path):
        """Test detection of missing space after ::"""
        test_file = tmp_path / "test.twee"
        test_file.write_text("::Start\n")

        violations, modified = lint(test_file, fix=False)
        assert len(violations) == 1
        assert 'passage-header-spacing' in violations[0]
        assert modified is False

    def test_fix_missing_space(self, tmp_path):
        """Test fixing missing space after ::"""
        test_file = tmp_path / "test.twee"
        test_file.write_text("::Start\n")

        violations, modified = lint(test_file, fix=True)
        assert len(violations) == 1
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content == ":: Start\n"

    def test_idempotent_fix(self, tmp_path):
        """Test that fixing twice produces same result."""
        test_file = tmp_path / "test.twee"
        test_file.write_text("::Start\n")

        lint(test_file, fix=True)
        violations2, modified2 = lint(test_file, fix=True)
        assert len(violations2) == 0
        assert modified2 is False


class TestBlankLineAfterHeader:
    """Tests for blank-line-after-header rule."""

    def test_detect_missing_blank_line(self, tmp_path):
        """Test detection of missing blank line after header."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\nSome text\n")

        violations, modified = lint(test_file, fix=False)
        assert any('blank-line-after-header' in v for v in violations)
        assert modified is False

    def test_fix_missing_blank_line(self, tmp_path):
        """Test fixing missing blank line after header."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\nSome text\n")

        violations, modified = lint(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content == ":: Start\n\nSome text\n"

    def test_special_passage_no_blank_line_needed(self, tmp_path):
        """Test that special passages don't need blank line."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: StoryData\n{}\n")

        violations, modified = lint(test_file, fix=False)
        # Should not have blank-line-after-header violation
        assert not any('blank-line-after-header' in v for v in violations)

    def test_stylesheet_tag_no_blank_line_needed(self, tmp_path):
        """Test that passages with stylesheet tag don't need blank line."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: MyStyles [stylesheet]\nbody { }\n")

        violations, modified = lint(test_file, fix=False)
        # Should not have blank-line-after-header violation
        assert not any('blank-line-after-header' in v for v in violations)


class TestBlankLineBetweenPassages:
    """Tests for blank-line-between-passages rule."""

    def test_detect_missing_blank_line(self, tmp_path):
        """Test detection of missing blank line between passages."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n:: Next\n\nMore text\n")

        violations, modified = lint(test_file, fix=False)
        assert any('blank-line-between-passages' in v for v in violations)

    def test_fix_missing_blank_line(self, tmp_path):
        """Test fixing missing blank line between passages."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n:: Next\n\nMore text\n")

        violations, modified = lint(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert "Text\n\n:: Next" in content

    def test_detect_too_many_blank_lines(self, tmp_path):
        """Test detection of too many blank lines between passages."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\n:: Next\n\nMore text\n")

        violations, modified = lint(test_file, fix=False)
        # Will be caught by either blank-line-between-passages or single-blank-lines
        assert len(violations) > 0

    def test_fix_too_many_blank_lines(self, tmp_path):
        """Test fixing too many blank lines between passages."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\n:: Next\n\nMore text\n")

        lint(test_file, fix=True)
        content = test_file.read_text()
        # Should have exactly one blank line between passages
        assert "Text\n\n:: Next" in content


class TestTrailingWhitespace:
    """Tests for trailing-whitespace rule."""

    def test_detect_trailing_spaces(self, tmp_path):
        """Test detection of trailing spaces."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText with spaces   \n")

        violations, modified = lint(test_file, fix=False)
        assert any('trailing-whitespace' in v for v in violations)

    def test_fix_trailing_spaces(self, tmp_path):
        """Test fixing trailing spaces."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText with spaces   \n")

        violations, modified = lint(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content == ":: Start\n\nText with spaces\n"

    def test_detect_trailing_tabs(self, tmp_path):
        """Test detection of trailing tabs."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText with tabs\t\t\n")

        violations, modified = lint(test_file, fix=False)
        assert any('trailing-whitespace' in v for v in violations)


class TestFinalNewline:
    """Tests for final-newline rule."""

    def test_detect_missing_final_newline(self, tmp_path):
        """Test detection of missing final newline."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText")

        violations, modified = lint(test_file, fix=False)
        assert any('final-newline' in v for v in violations)

    def test_fix_missing_final_newline(self, tmp_path):
        """Test fixing missing final newline."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText")

        violations, modified = lint(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content.endswith('\n')

    def test_detect_multiple_trailing_newlines(self, tmp_path):
        """Test detection of multiple trailing newlines."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\n")

        violations, modified = lint(test_file, fix=False)
        assert any('final-newline' in v for v in violations)

    def test_fix_multiple_trailing_newlines(self, tmp_path):
        """Test fixing multiple trailing newlines."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\n")

        violations, modified = lint(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content == ":: Start\n\nText\n"


class TestSingleBlankLines:
    """Tests for single-blank-lines rule."""

    def test_detect_multiple_blank_lines(self, tmp_path):
        """Test detection of multiple consecutive blank lines."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\nMore text\n")

        violations, modified = lint(test_file, fix=False)
        # Note: In check mode, this rule only reports in fix mode
        # So we need to run in fix mode to detect
        violations, modified = lint(test_file, fix=True)
        assert any('single-blank-lines' in v for v in violations)

    def test_fix_multiple_blank_lines(self, tmp_path):
        """Test fixing multiple consecutive blank lines."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\nMore text\n")

        violations, modified = lint(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content == ":: Start\n\nText\n\nMore text\n"

    def test_idempotent_fix(self, tmp_path):
        """Test that fixing twice produces same result."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\nMore text\n")

        lint(test_file, fix=True)
        violations2, modified2 = lint(test_file, fix=True)
        assert len(violations2) == 0
        assert modified2 is False


class TestLinkBlockSpacing:
    """Tests for link-block-spacing rule."""

    def test_detect_missing_blank_before_link_block(self, tmp_path):
        """Test detection of missing blank line before link block."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some narrative text.\n"
            "[[Continue]]\n"
        )

        violations, modified = lint(test_file, fix=False)
        assert any('link-block-spacing' in v and 'before' in v for v in violations)

    def test_fix_missing_blank_before_link_block(self, tmp_path):
        """Test fixing missing blank line before link block."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some narrative text.\n"
            "[[Continue]]\n"
        )

        violations, modified = lint(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert "Some narrative text.\n\n[[Continue]]" in content

    def test_detect_missing_blank_after_link_block(self, tmp_path):
        """Test detection of missing blank line after link block."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some text.\n\n"
            "[[Continue]]\n"
            "More text.\n"
        )

        violations, modified = lint(test_file, fix=False)
        assert any('link-block-spacing' in v and 'after' in v for v in violations)

    def test_fix_missing_blank_after_link_block(self, tmp_path):
        """Test fixing missing blank line after link block."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some text.\n\n"
            "[[Continue]]\n"
            "More text.\n"
        )

        violations, modified = lint(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert "[[Continue]]\n\nMore text" in content

    def test_detect_blank_between_block_links(self, tmp_path):
        """Test detection of blank line between block links."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some text.\n\n"
            "[[Option 1]]\n\n"
            "[[Option 2]]\n"
        )

        violations, modified = lint(test_file, fix=False)
        assert any('link-block-spacing' in v and 'between' in v for v in violations)

    def test_fix_blank_between_block_links(self, tmp_path):
        """Test fixing blank line between block links."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some text.\n\n"
            "[[Option 1]]\n\n"
            "[[Option 2]]\n"
        )

        violations, modified = lint(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert "[[Option 1]]\n[[Option 2]]" in content

    def test_multiple_block_links_properly_formatted(self, tmp_path):
        """Test that properly formatted link blocks have no violations."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some narrative text.\n\n"
            "[[Option 1]]\n"
            "[[Option 2]]\n"
            "[[Option 3]]\n\n"
            "More text.\n"
        )

        violations, modified = lint(test_file, fix=False)
        # Should have no link-block-spacing violations
        assert not any('link-block-spacing' in v for v in violations)

    def test_inline_links_not_affected(self, tmp_path):
        """Test that inline links are not treated as block links."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "You can [[continue]] or [[go back]].\n"
        )

        violations, modified = lint(test_file, fix=False)
        # Should have no link-block-spacing violations
        assert not any('link-block-spacing' in v for v in violations)

    def test_link_block_right_after_header(self, tmp_path):
        """Test that link blocks right after headers work correctly."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "[[Continue]]\n"
        )

        violations, modified = lint(test_file, fix=False)
        # Should have no link-block-spacing violations (no narrative before)
        assert not any('link-block-spacing' in v for v in violations)

    def test_link_block_ends_passage(self, tmp_path):
        """Test that link blocks at end of passage work correctly."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some text.\n\n"
            "[[Continue]]\n\n"
            ":: Next\n\n"
            "More text.\n"
        )

        violations, modified = lint(test_file, fix=False)
        # Should have no link-block-spacing violations
        # (passage boundary handles spacing)
        assert not any('link-block-spacing' in v for v in violations)

    def test_complex_passage_with_link_blocks(self, tmp_path):
        """Test complex passage with multiple link blocks."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Opening narrative.\n\n"
            "[[Choice A]]\n"
            "[[Choice B]]\n\n"
            "Middle narrative.\n\n"
            "[[Choice C]]\n"
            "[[Choice D]]\n"
        )

        violations, modified = lint(test_file, fix=False)
        # Should have no link-block-spacing violations
        assert not any('link-block-spacing' in v for v in violations)

    def test_idempotent_fix(self, tmp_path):
        """Test that fixing twice produces same result."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some text.\n"
            "[[Option 1]]\n\n"
            "[[Option 2]]\n"
            "More text.\n"
        )

        lint(test_file, fix=True)
        violations2, modified2 = lint(test_file, fix=True)
        assert len(violations2) == 0
        assert modified2 is False


class TestIntegration:
    """Integration tests combining multiple rules."""

    def test_full_file_all_violations(self, tmp_path):
        """Test file with all types of violations."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            "::Start   \n"  # Missing space, trailing whitespace
            "Text\n"  # Missing blank after header
            ":: Next\n"  # Missing blank before header
            "More text\n"
            "[[Link1]]\n\n"  # Blank between links
            "[[Link2]]"  # Missing final newline
        )

        violations, modified = lint(test_file, fix=True)
        assert len(violations) > 0
        assert modified is True

        # Verify all issues fixed
        violations2, modified2 = lint(test_file, fix=True)
        assert len(violations2) == 0
        assert modified2 is False

    def test_properly_formatted_file(self, tmp_path):
        """Test file that is already properly formatted."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Opening narrative text.\n\n"
            "[[Option 1]]\n"
            "[[Option 2]]\n\n"
            ":: Next\n\n"
            "More text.\n"
        )

        violations, modified = lint(test_file, fix=False)
        assert len(violations) == 0
        assert modified is False

    def test_empty_file(self, tmp_path):
        """Test that empty files are valid."""
        test_file = tmp_path / "test.twee"
        test_file.write_text("")

        violations, modified = lint(test_file, fix=False)
        assert len(violations) == 0
        assert modified is False

    def test_file_with_only_header(self, tmp_path):
        """Test file with only a passage header."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n")

        violations, modified = lint(test_file, fix=False)
        # Should have violations for missing content structure
        # But should not crash
        assert isinstance(violations, list)


class TestSmartQuotesAreAllowed:
    """The 2025 smart-quotes rule rewrote prose; it is removed."""

    def test_curly_quotes_are_not_reported(self, tmp_path):
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\n\u201cHe said, \u2018Yes\u2019\u201d\n", encoding="utf-8")
        violations, modified = lint(test_file, fix=False)
        assert violations == []
        assert fix_file(test_file) == []
        assert "\u201c" in test_file.read_text(encoding="utf-8")


class TestViolation:
    def test_text_and_github_forms(self):
        violation = Violation(Path("src/AB-20251101.twee"), 3, "trailing-whitespace", "Line has trailing whitespace")
        assert str(violation) == "src/AB-20251101.twee:3: [trailing-whitespace] Line has trailing whitespace"
        assert violation.github() == (
            "::warning file=src/AB-20251101.twee,line=3,title=trailing-whitespace::Line has trailing whitespace"
        )

    def test_violation_fields(self, tmp_path):
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText   \n")
        assert lint_file(test_file) == [
            Violation(test_file, 3, "trailing-whitespace", "Line has trailing whitespace")
        ]


class TestFixText:
    def test_returns_input_unchanged_when_clean(self):
        text = ":: Start\n\nClean.\n"
        assert fix_text(text, Path("x.twee")) == (text, [])

    def test_crlf_is_normalized_when_fixing(self):
        fixed, violations = fix_text(":: Start\r\nText\r\n", Path("x.twee"))
        assert fixed == ":: Start\n\nText\n"
        assert [v.rule for v in violations] == ["blank-line-after-header"]


class TestLintPath:
    def test_directory_is_recursive_and_sorted(self, tmp_path):
        (tmp_path / "b.twee").write_text("::B\n")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.twee").write_text(":: A\n\nText  \n")
        (tmp_path / "notes.txt").write_text("::not twee  \n")
        violations = lint_path(tmp_path)
        assert [(v.file.name, v.rule) for v in violations] == [
            ("b.twee", "passage-header-spacing"),
            ("a.twee", "trailing-whitespace"),
        ]

    def test_missing_path_is_an_error(self, tmp_path):
        with pytest.raises(LintError, match="does not exist"):
            lint_path(tmp_path / "nope.twee")

    def test_non_twee_file_is_an_error(self, tmp_path):
        other = tmp_path / "notes.txt"
        other.write_text("x")
        with pytest.raises(LintError, match="not a .twee file"):
            lint_path(other)

    def test_undecodable_file_is_an_error(self, tmp_path):
        bad = tmp_path / "bad.twee"
        bad.write_bytes(b":: Start\n\n\xff\xfe\n")
        with pytest.raises(LintError, match="cannot read"):
            lint_path(bad)


class TestLintCli:
    def test_reports_without_editing_and_exits_1(self, tmp_path, capsys):
        test_file = tmp_path / "test.twee"
        test_file.write_text("::Start\nText\n")
        assert main(["lint", str(tmp_path)]) == 1
        captured = capsys.readouterr()
        assert "[passage-header-spacing]" in captured.out
        assert "2 formatting issue(s) in 1 file(s)" in captured.err
        assert test_file.read_text() == "::Start\nText\n"

    def test_clean_tree_exits_0(self, tmp_path, capsys):
        (tmp_path / "test.twee").write_text(":: Start\n\nText\n")
        assert main(["lint", str(tmp_path)]) == 0
        assert "0 formatting issue(s)" in capsys.readouterr().err

    def test_github_format(self, tmp_path, capsys):
        (tmp_path / "test.twee").write_text(":: Start\n\nText \n")
        assert main(["lint", str(tmp_path), "--format", "github"]) == 1
        assert capsys.readouterr().out.startswith("::warning file=")

    def test_there_is_no_fix_flag(self, tmp_path, capsys):
        (tmp_path / "test.twee").write_text("::Start\n")
        with pytest.raises(SystemExit) as exc:
            main(["lint", str(tmp_path), "--fix"])
        assert exc.value.code == 2
        assert (tmp_path / "test.twee").read_text() == "::Start\n"

    def test_missing_path_reports_error(self, tmp_path, capsys):
        assert main(["lint", str(tmp_path / "nope")]) == 1
        assert "error:" in capsys.readouterr().err
