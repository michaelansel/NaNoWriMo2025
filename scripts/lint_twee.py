#!/usr/bin/env python3
"""
Twee passage formatting linter.

This script lints .twee files for common formatting issues and can automatically
fix them. It enforces consistent formatting across all Twee story files.

Rules enforced:
1. passage-header-spacing: Space after :: in passage headers
2. blank-line-after-header: Blank line after passage headers (with exceptions)
3. blank-line-between-passages: Exactly one blank line before passage headers
4. trailing-whitespace: No trailing whitespace on lines
5. final-newline: File ends with exactly one newline
6. single-blank-lines: No multiple consecutive blank lines
7. link-block-spacing: Blank line before and after link blocks, no blanks between links
8. smart-quotes: Replace Unicode smart quotes with ASCII equivalents

Special passages exempt from blank-line-after-header:
- By name: StoryData, StoryTitle, StoryStylesheet, StoryBanner, StoryMenu, StoryInit
- By tag: [stylesheet], [script]
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import re

# Exit codes
EXIT_SUCCESS = 0
EXIT_VIOLATIONS = 1
EXIT_ERROR = 2

# Special passages that don't need blank line after header
SPECIAL_PASSAGE_NAMES = {
    'StoryData',
    'StoryTitle',
    'StoryStylesheet',
    'StoryBanner',
    'StoryMenu',
    'StoryInit'
}

SPECIAL_PASSAGE_TAGS = {
    'stylesheet',
    'script'
}


def parse_passage_header(line: str) -> Optional[Tuple[str, List[str]]]:
    """
    Parse a passage header line and extract name and tags.

    Args:
        line: A line that might be a passage header

    Returns:
        Tuple of (passage_name, tags_list) if valid header, None otherwise

    Examples:
        >>> parse_passage_header(":: Start")
        ('Start', [])
        >>> parse_passage_header(":: StoryStylesheet [stylesheet]")
        ('StoryStylesheet', ['stylesheet'])
        >>> parse_passage_header("::No space")
        ('No space', [])
        >>> parse_passage_header("Not a header")
        None
    """
    if not line.startswith('::'):
        return None

    # Remove :: prefix
    content = line[2:].strip()

    # Check for tags in square brackets
    tag_match = re.search(r'\[([^\]]+)\]', content)
    if tag_match:
        tags_str = tag_match.group(1)
        tags = [tag.strip() for tag in tags_str.split()]
        # Remove tags from passage name
        passage_name = content[:tag_match.start()].strip()
    else:
        tags = []
        passage_name = content

    return (passage_name, tags)


def is_special_passage(passage_name: str, tags: List[str]) -> bool:
    """
    Check if a passage is special (exempt from blank-line-after-header).

    Args:
        passage_name: The name of the passage
        tags: List of tags on the passage

    Returns:
        True if passage is special, False otherwise
    """
    if passage_name in SPECIAL_PASSAGE_NAMES:
        return True

    for tag in tags:
        if tag in SPECIAL_PASSAGE_TAGS:
            return True

    return False


def is_block_link(line: str) -> bool:
    """
    Check if a line contains only a block link (no other text).

    A block link is a line that contains only [[...]] with optional whitespace.
    Inline links (links with other text) are not block links.

    Args:
        line: The line to check (should be stripped of trailing whitespace)

    Returns:
        True if line is a block link, False otherwise

    Examples:
        >>> is_block_link("[[Continue]]")
        True
        >>> is_block_link("  [[Continue->Next]]  ")
        True
        >>> is_block_link("Text before [[link]]")
        False
        >>> is_block_link("[[link]] text after")
        False
        >>> is_block_link("[[link1]] [[link2]]")
        False
        >>> is_block_link("[]")
        False
        >>> is_block_link("")
        False
    """
    stripped = line.strip()
    if not stripped:
        return False

    # Must start with [[ and end with ]]
    if not (stripped.startswith('[[') and stripped.endswith(']]')):
        return False

    # Must have content between the brackets (not just [[]])
    if len(stripped) <= 4:  # [[]] is 4 characters
        return False

    # Count occurrences - should have exactly one [[ and one ]]
    if stripped.count('[[') != 1 or stripped.count(']]') != 1:
        return False

    # The whole stripped line should be the link (no text before/after)
    return True


def lint_file(file_path: Path, fix: bool = False) -> Tuple[List[str], bool]:
    """
    Lint a single .twee file.

    Args:
        file_path: Path to the .twee file
        fix: If True, automatically fix issues

    Returns:
        Tuple of (violations_list, was_modified)
        - violations_list: List of violation strings (empty if no issues)
        - was_modified: True if file was modified (only relevant when fix=True)

    Implementation notes:
    - Idempotent: Running fix twice produces same result
    - Preserves UTF-8 encoding
    - Processes file line-by-line to maintain memory efficiency
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return [f"Error reading file: {e}"], False

    if not lines:
        # Empty file is valid
        return [], False

    violations = []
    fixed_lines = []
    line_num = 0
    last_was_header = False
    last_passage_info = None  # (name, tags) of last passage header
    last_was_block_link = False
    in_link_block = False
    last_non_blank_was_narrative = False  # Track if we just had narrative text

    for i, line in enumerate(lines):
        line_num = i + 1
        original_line = line
        # Remove line ending for processing
        line_content = line.rstrip('\n\r')

        # Rule 4: trailing-whitespace
        if line_content and line_content != line_content.rstrip():
            violations.append(
                f"{file_path}:{line_num}: [trailing-whitespace] "
                f"Line has trailing whitespace"
            )
            if fix:
                line_content = line_content.rstrip()

        # Rule 8: smart-quotes
        # Replace Unicode smart quotes with ASCII equivalents
        smart_quotes = {
            '\u201c': '"',  # Left double quotation mark
            '\u201d': '"',  # Right double quotation mark
            '\u2018': "'",  # Left single quotation mark
            '\u2019': "'",  # Right single quotation mark
        }
        smart_quote_count = sum(line_content.count(sq) for sq in smart_quotes.keys())
        if smart_quote_count > 0:
            violations.append(
                f"{file_path}:{line_num}: [smart-quotes] "
                f"Found {smart_quote_count} smart quote(s)"
            )
            if fix:
                for smart, ascii_equiv in smart_quotes.items():
                    line_content = line_content.replace(smart, ascii_equiv)

        # Rule 7: link-block-spacing
        # Check if current line is a block link
        current_is_block_link = is_block_link(line_content)
        current_is_blank = line_content.strip() == ''

        if current_is_block_link:
            # Entering a link block
            if not in_link_block:
                # First block link in a sequence
                # Need blank line before if narrative preceded (not right after header)
                if last_non_blank_was_narrative and fixed_lines:
                    # Check if there's a blank line before this
                    if fixed_lines and fixed_lines[-1].strip() != '':
                        violations.append(
                            f"{file_path}:{line_num}: [link-block-spacing] "
                            f"Missing blank line before link block"
                        )
                        if fix:
                            fixed_lines.append('')
                in_link_block = True
            else:
                # Consecutive block link - remove blank line if present
                if fixed_lines and fixed_lines[-1].strip() == '':
                    violations.append(
                        f"{file_path}:{line_num}: [link-block-spacing] "
                        f"Blank line between block links (should be removed)"
                    )
                    if fix:
                        # Remove the blank line we just added
                        fixed_lines.pop()

            last_was_block_link = True
            last_non_blank_was_narrative = False

        elif not current_is_blank:
            # Non-blank, non-block-link line
            # If exiting a link block, need blank line before this
            if in_link_block and not line_content.startswith('::'):
                # Check if there's a blank line before this
                if fixed_lines and fixed_lines[-1].strip() != '':
                    violations.append(
                        f"{file_path}:{line_num}: [link-block-spacing] "
                        f"Missing blank line after link block"
                    )
                    if fix:
                        fixed_lines.append('')

            in_link_block = False
            last_was_block_link = False

            # Track if this is narrative (not a header or special line)
            if not line_content.startswith('::'):
                last_non_blank_was_narrative = True
        else:
            # Blank line
            last_non_blank_was_narrative = False

        # Check if this is a passage header
        if line_content.startswith('::'):
            parsed = parse_passage_header(line_content)
            if parsed:
                passage_name, tags = parsed

                # Rule 1: passage-header-spacing
                # Check if there's a space after ::
                if not line_content.startswith(':: ') and len(line_content) > 2:
                    violations.append(
                        f"{file_path}:{line_num}: [passage-header-spacing] "
                        f"Missing space after :: in passage header"
                    )
                    if fix:
                        # Add space after ::
                        line_content = ':: ' + line_content[2:].lstrip()

                # Rule 3: blank-line-between-passages
                # Check if there's exactly one blank line before this header
                # (skip for first passage in file)
                if fixed_lines:
                    # Count blank lines before this header
                    blank_count = 0
                    for j in range(len(fixed_lines) - 1, -1, -1):
                        if fixed_lines[j].strip() == '':
                            blank_count += 1
                        else:
                            break

                    if blank_count != 1:
                        violations.append(
                            f"{file_path}:{line_num}: [blank-line-between-passages] "
                            f"Expected exactly 1 blank line before passage header, found {blank_count}"
                        )
                        if fix:
                            # Remove excess blank lines or add missing one
                            while blank_count > 1 and fixed_lines and fixed_lines[-1].strip() == '':
                                fixed_lines.pop()
                                blank_count -= 1
                            if blank_count == 0:
                                fixed_lines.append('')

                last_was_header = True
                last_passage_info = (passage_name, tags)
                # Reset link block state on passage header
                in_link_block = False
                last_was_block_link = False
                last_non_blank_was_narrative = False
            else:
                last_was_header = False
        else:
            # Rule 2: blank-line-after-header
            # Check if previous line was a header and this line is not blank
            if last_was_header and line_content.strip() != '':
                if last_passage_info:
                    passage_name, tags = last_passage_info
                    if not is_special_passage(passage_name, tags):
                        violations.append(
                            f"{file_path}:{line_num - 1}: [blank-line-after-header] "
                            f"Missing blank line after passage header"
                        )
                        if fix:
                            # Insert blank line before current line
                            fixed_lines.append('')

            last_was_header = False

        # Rule 6: single-blank-lines
        # Collapse multiple consecutive blank lines
        if fix and line_content.strip() == '':
            # Check if previous line was also blank
            if fixed_lines and fixed_lines[-1].strip() == '':
                # Skip this blank line (collapsing multiples)
                violations.append(
                    f"{file_path}:{line_num}: [single-blank-lines] "
                    f"Multiple consecutive blank lines"
                )
                continue

        fixed_lines.append(line_content)

    # Rule 5: final-newline
    # File should end with exactly one newline
    if fixed_lines:
        # Count trailing blank lines
        trailing_blanks = 0
        check_index = len(fixed_lines) - 1
        while check_index >= 0 and fixed_lines[check_index].strip() == '':
            trailing_blanks += 1
            check_index -= 1

        if trailing_blanks > 1:
            violations.append(
                f"{file_path}:{len(lines)}: [final-newline] "
                f"File has {trailing_blanks} trailing blank lines, expected 0"
            )

        # Remove trailing blank lines if fixing
        if fix:
            while fixed_lines and fixed_lines[-1].strip() == '':
                fixed_lines.pop()

        # Check if original file ended with newline
        original_ends_with_newline = lines[-1].endswith('\n') or lines[-1].endswith('\r\n')
        if not original_ends_with_newline:
            violations.append(
                f"{file_path}:{len(lines)}: [final-newline] "
                f"File does not end with newline"
            )

    # Write fixed content if requested
    was_modified = False
    if fix and violations:
        try:
            # Join lines with newline and ensure final newline
            content = '\n'.join(fixed_lines)
            if content:  # Only add final newline if file is non-empty
                content += '\n'

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            was_modified = True
        except Exception as e:
            violations.append(f"Error writing file: {e}")
            return violations, False

    return violations, was_modified


def lint_directory(directory: Path, fix: bool = False) -> Tuple[int, int, int]:
    """
    Lint all .twee files in a directory recursively.

    Args:
        directory: Directory to search for .twee files
        fix: If True, automatically fix issues

    Returns:
        Tuple of (total_files, files_with_violations, total_violations)
    """
    total_files = 0
    files_with_violations = 0
    total_violations = 0

    for twee_file in sorted(directory.rglob('*.twee')):
        total_files += 1
        violations, was_modified = lint_file(twee_file, fix=fix)

        if violations:
            files_with_violations += 1
            total_violations += len(violations)

            # Print violations
            for violation in violations:
                if fix and was_modified and not violation.startswith("Error"):
                    # Mark as fixed
                    print(violation.replace(']', '] [FIXED]', 1))
                else:
                    print(violation)

    return total_files, files_with_violations, total_violations


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description='Lint Twee passage formatting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check files for violations
  %(prog)s src/

  # Fix violations automatically
  %(prog)s src/ --fix

Exit codes:
  0 - Success (no violations or all fixed)
  1 - Violations found (check mode)
  2 - Error occurred
        """
    )

    parser.add_argument('path', type=Path,
                        help='File or directory to lint')
    parser.add_argument('--fix', action='store_true',
                        help='Automatically fix violations')

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: {args.path} does not exist", file=sys.stderr)
        return EXIT_ERROR

    # Handle single file
    if args.path.is_file():
        if not args.path.suffix == '.twee':
            print(f"Error: {args.path} is not a .twee file", file=sys.stderr)
            return EXIT_ERROR

        violations, was_modified = lint_file(args.path, fix=args.fix)

        for violation in violations:
            if args.fix and was_modified and not violation.startswith("Error"):
                print(violation.replace(']', '] [FIXED]', 1))
            else:
                print(violation)

        if violations:
            if args.fix and was_modified:
                return EXIT_SUCCESS  # Fixed successfully
            else:
                return EXIT_VIOLATIONS  # Found violations in check mode
        return EXIT_SUCCESS

    # Handle directory
    if args.path.is_dir():
        total_files, files_with_violations, total_violations = lint_directory(
            args.path, fix=args.fix
        )

        # Print summary
        print(f"\nLinted {total_files} file(s)", file=sys.stderr)
        if args.fix:
            print(f"Fixed {files_with_violations} file(s) with {total_violations} violation(s)",
                  file=sys.stderr)
        else:
            print(f"Found {total_violations} violation(s) in {files_with_violations} file(s)",
                  file=sys.stderr)

        if total_violations > 0 and not args.fix:
            return EXIT_VIOLATIONS

        return EXIT_SUCCESS

    print(f"Error: {args.path} is neither a file nor directory", file=sys.stderr)
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
