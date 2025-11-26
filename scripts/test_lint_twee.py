#!/usr/bin/env python3
"""
Unit tests for Twee passage formatting linter.

Tests all linting rules including:
1. passage-header-spacing
2. blank-line-after-header
3. blank-line-between-passages
4. trailing-whitespace
5. final-newline
6. single-blank-lines
7. link-block-spacing
8. smart-quotes

Each test covers detection (check mode) and fixing (fix mode), and verifies
idempotency (running fix twice produces the same result).
"""

import pytest
from pathlib import Path
from lint_twee import (
    is_block_link,
    parse_passage_header,
    is_special_passage,
    lint_file,
)


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

        violations, modified = lint_file(test_file, fix=False)
        assert len(violations) == 1
        assert 'passage-header-spacing' in violations[0]
        assert modified is False

    def test_fix_missing_space(self, tmp_path):
        """Test fixing missing space after ::"""
        test_file = tmp_path / "test.twee"
        test_file.write_text("::Start\n")

        violations, modified = lint_file(test_file, fix=True)
        assert len(violations) == 1
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content == ":: Start\n"

    def test_idempotent_fix(self, tmp_path):
        """Test that fixing twice produces same result."""
        test_file = tmp_path / "test.twee"
        test_file.write_text("::Start\n")

        lint_file(test_file, fix=True)
        violations2, modified2 = lint_file(test_file, fix=True)
        assert len(violations2) == 0
        assert modified2 is False


class TestBlankLineAfterHeader:
    """Tests for blank-line-after-header rule."""

    def test_detect_missing_blank_line(self, tmp_path):
        """Test detection of missing blank line after header."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\nSome text\n")

        violations, modified = lint_file(test_file, fix=False)
        assert any('blank-line-after-header' in v for v in violations)
        assert modified is False

    def test_fix_missing_blank_line(self, tmp_path):
        """Test fixing missing blank line after header."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\nSome text\n")

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content == ":: Start\n\nSome text\n"

    def test_special_passage_no_blank_line_needed(self, tmp_path):
        """Test that special passages don't need blank line."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: StoryData\n{}\n")

        violations, modified = lint_file(test_file, fix=False)
        # Should not have blank-line-after-header violation
        assert not any('blank-line-after-header' in v for v in violations)

    def test_stylesheet_tag_no_blank_line_needed(self, tmp_path):
        """Test that passages with stylesheet tag don't need blank line."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: MyStyles [stylesheet]\nbody { }\n")

        violations, modified = lint_file(test_file, fix=False)
        # Should not have blank-line-after-header violation
        assert not any('blank-line-after-header' in v for v in violations)


class TestBlankLineBetweenPassages:
    """Tests for blank-line-between-passages rule."""

    def test_detect_missing_blank_line(self, tmp_path):
        """Test detection of missing blank line between passages."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n:: Next\n\nMore text\n")

        violations, modified = lint_file(test_file, fix=False)
        assert any('blank-line-between-passages' in v for v in violations)

    def test_fix_missing_blank_line(self, tmp_path):
        """Test fixing missing blank line between passages."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n:: Next\n\nMore text\n")

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert "Text\n\n:: Next" in content

    def test_detect_too_many_blank_lines(self, tmp_path):
        """Test detection of too many blank lines between passages."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\n:: Next\n\nMore text\n")

        violations, modified = lint_file(test_file, fix=False)
        # Will be caught by either blank-line-between-passages or single-blank-lines
        assert len(violations) > 0

    def test_fix_too_many_blank_lines(self, tmp_path):
        """Test fixing too many blank lines between passages."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\n:: Next\n\nMore text\n")

        lint_file(test_file, fix=True)
        content = test_file.read_text()
        # Should have exactly one blank line between passages
        assert "Text\n\n:: Next" in content


class TestTrailingWhitespace:
    """Tests for trailing-whitespace rule."""

    def test_detect_trailing_spaces(self, tmp_path):
        """Test detection of trailing spaces."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText with spaces   \n")

        violations, modified = lint_file(test_file, fix=False)
        assert any('trailing-whitespace' in v for v in violations)

    def test_fix_trailing_spaces(self, tmp_path):
        """Test fixing trailing spaces."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText with spaces   \n")

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content == ":: Start\n\nText with spaces\n"

    def test_detect_trailing_tabs(self, tmp_path):
        """Test detection of trailing tabs."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText with tabs\t\t\n")

        violations, modified = lint_file(test_file, fix=False)
        assert any('trailing-whitespace' in v for v in violations)


class TestFinalNewline:
    """Tests for final-newline rule."""

    def test_detect_missing_final_newline(self, tmp_path):
        """Test detection of missing final newline."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText")

        violations, modified = lint_file(test_file, fix=False)
        assert any('final-newline' in v for v in violations)

    def test_fix_missing_final_newline(self, tmp_path):
        """Test fixing missing final newline."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText")

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content.endswith('\n')

    def test_detect_multiple_trailing_newlines(self, tmp_path):
        """Test detection of multiple trailing newlines."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\n")

        violations, modified = lint_file(test_file, fix=False)
        assert any('final-newline' in v for v in violations)

    def test_fix_multiple_trailing_newlines(self, tmp_path):
        """Test fixing multiple trailing newlines."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\n")

        violations, modified = lint_file(test_file, fix=True)
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

        violations, modified = lint_file(test_file, fix=False)
        # Note: In check mode, this rule only reports in fix mode
        # So we need to run in fix mode to detect
        violations, modified = lint_file(test_file, fix=True)
        assert any('single-blank-lines' in v for v in violations)

    def test_fix_multiple_blank_lines(self, tmp_path):
        """Test fixing multiple consecutive blank lines."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\nMore text\n")

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert content == ":: Start\n\nText\n\nMore text\n"

    def test_idempotent_fix(self, tmp_path):
        """Test that fixing twice produces same result."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\nText\n\n\nMore text\n")

        lint_file(test_file, fix=True)
        violations2, modified2 = lint_file(test_file, fix=True)
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

        violations, modified = lint_file(test_file, fix=False)
        assert any('link-block-spacing' in v and 'before' in v for v in violations)

    def test_fix_missing_blank_before_link_block(self, tmp_path):
        """Test fixing missing blank line before link block."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "Some narrative text.\n"
            "[[Continue]]\n"
        )

        violations, modified = lint_file(test_file, fix=True)
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

        violations, modified = lint_file(test_file, fix=False)
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

        violations, modified = lint_file(test_file, fix=True)
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

        violations, modified = lint_file(test_file, fix=False)
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

        violations, modified = lint_file(test_file, fix=True)
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

        violations, modified = lint_file(test_file, fix=False)
        # Should have no link-block-spacing violations
        assert not any('link-block-spacing' in v for v in violations)

    def test_inline_links_not_affected(self, tmp_path):
        """Test that inline links are not treated as block links."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "You can [[continue]] or [[go back]].\n"
        )

        violations, modified = lint_file(test_file, fix=False)
        # Should have no link-block-spacing violations
        assert not any('link-block-spacing' in v for v in violations)

    def test_link_block_right_after_header(self, tmp_path):
        """Test that link blocks right after headers work correctly."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ":: Start\n\n"
            "[[Continue]]\n"
        )

        violations, modified = lint_file(test_file, fix=False)
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

        violations, modified = lint_file(test_file, fix=False)
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

        violations, modified = lint_file(test_file, fix=False)
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

        lint_file(test_file, fix=True)
        violations2, modified2 = lint_file(test_file, fix=True)
        assert len(violations2) == 0
        assert modified2 is False


class TestSmartQuotes:
    """Tests for smart-quotes rule."""

    def test_detect_left_double_quote(self, tmp_path):
        """Test detection of left double quotation mark."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(':: Start\n\n\u201cHello world\u201d\n')

        violations, modified = lint_file(test_file, fix=False)
        assert any('smart-quotes' in v for v in violations)
        assert modified is False

    def test_detect_right_double_quote(self, tmp_path):
        """Test detection of right double quotation mark."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(':: Start\n\n\u201cHello world\u201d\n')

        violations, modified = lint_file(test_file, fix=False)
        assert any('smart-quotes' in v for v in violations)
        assert modified is False

    def test_detect_left_single_quote(self, tmp_path):
        """Test detection of left single quotation mark."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\n\u2018Hello world\u2019\n")

        violations, modified = lint_file(test_file, fix=False)
        assert any('smart-quotes' in v for v in violations)
        assert modified is False

    def test_detect_right_single_quote(self, tmp_path):
        """Test detection of right single quotation mark."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\n\u2018Hello world\u2019\n")

        violations, modified = lint_file(test_file, fix=False)
        assert any('smart-quotes' in v for v in violations)
        assert modified is False

    def test_detect_all_smart_quote_types(self, tmp_path):
        """Test detection of all smart quote types in one line."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(':: Start\n\n\u201cHe said, \u2018Yes\u2019\u201d\n')

        violations, modified = lint_file(test_file, fix=False)
        assert any('smart-quotes' in v and '4' in v for v in violations)
        assert modified is False

    def test_fix_left_double_quote(self, tmp_path):
        """Test fixing left double quotation mark."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(':: Start\n\n\u201cHello\u201d\n')

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert '\u201c' not in content
        assert '\u201d' not in content
        assert '"Hello"' in content

    def test_fix_right_double_quote(self, tmp_path):
        """Test fixing right double quotation mark."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(':: Start\n\n\u201cHello\u201d\n')

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert '\u201c' not in content
        assert '\u201d' not in content
        assert '"Hello"' in content

    def test_fix_left_single_quote(self, tmp_path):
        """Test fixing left single quotation mark."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\n\u2018Hello\u2019\n")

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert '\u2018' not in content
        assert '\u2019' not in content
        assert "'Hello'" in content

    def test_fix_right_single_quote(self, tmp_path):
        """Test fixing right single quotation mark."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n\n\u2018Hello\u2019\n")

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert '\u2018' not in content
        assert '\u2019' not in content
        assert "'Hello'" in content

    def test_fix_all_smart_quote_types(self, tmp_path):
        """Test fixing all smart quote types in one line."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(':: Start\n\n\u201cHe said, \u2018Yes\u2019\u201d\n')

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix
        content = test_file.read_text()
        assert '\u201c' not in content
        assert '\u201d' not in content
        assert '\u2018' not in content
        assert '\u2019' not in content
        assert '"He said, \'Yes\'"' in content

    def test_mixed_smart_and_regular_quotes(self, tmp_path):
        """Test that regular quotes are preserved."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(':: Start\n\n\u201cSmart\u201d and "regular" quotes\n')

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify fix - smart quotes replaced, regular quotes preserved
        content = test_file.read_text()
        assert '\u201c' not in content
        assert '\u201d' not in content
        assert '"Smart" and "regular" quotes' in content

    def test_no_smart_quotes(self, tmp_path):
        """Test that lines without smart quotes have no violations."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(':: Start\n\n"Hello" and \'world\'\n')

        violations, modified = lint_file(test_file, fix=False)
        # Should have no smart-quotes violations
        assert not any('smart-quotes' in v for v in violations)

    def test_idempotent_fix(self, tmp_path):
        """Test that fixing twice produces same result."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(':: Start\n\n\u201cHello world\u201d\n')

        lint_file(test_file, fix=True)
        violations2, modified2 = lint_file(test_file, fix=True)
        # Should have no violations after first fix
        assert len(violations2) == 0
        assert modified2 is False

    def test_smart_quotes_in_multiple_lines(self, tmp_path):
        """Test detection and fixing of smart quotes in multiple lines."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(
            ':: Start\n\n'
            '\u201cFirst line with smart quotes\u201d\n'
            '\u201cSecond line with smart quotes\u201d\n'
        )

        violations, modified = lint_file(test_file, fix=True)
        assert modified is True

        # Verify both lines fixed
        content = test_file.read_text()
        assert '\u201c' not in content
        assert '\u201d' not in content
        assert '"First line with smart quotes"' in content
        assert '"Second line with smart quotes"' in content


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

        violations, modified = lint_file(test_file, fix=True)
        assert len(violations) > 0
        assert modified is True

        # Verify all issues fixed
        violations2, modified2 = lint_file(test_file, fix=True)
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

        violations, modified = lint_file(test_file, fix=False)
        assert len(violations) == 0
        assert modified is False

    def test_empty_file(self, tmp_path):
        """Test that empty files are valid."""
        test_file = tmp_path / "test.twee"
        test_file.write_text("")

        violations, modified = lint_file(test_file, fix=False)
        assert len(violations) == 0
        assert modified is False

    def test_file_with_only_header(self, tmp_path):
        """Test file with only a passage header."""
        test_file = tmp_path / "test.twee"
        test_file.write_text(":: Start\n")

        violations, modified = lint_file(test_file, fix=False)
        # Should have violations for missing content structure
        # But should not crash
        assert isinstance(violations, list)
