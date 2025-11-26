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
        # Remove trailing blank lines
        trailing_blanks = 0
        while fixed_lines and fixed_lines[-1].strip() == '':
            trailing_blanks += 1
            if fix:
                fixed_lines.pop()
            else:
                break

        if not fix and trailing_blanks > 1:
            violations.append(
                f"{file_path}:{len(lines)}: [final-newline] "
                f"File has {trailing_blanks} trailing blank lines, expected 0"
            )

        # Check if original file ended with newline
        original_ends_with_newline = lines[-1].endswith('\n') or lines[-1].endswith('\r\n')
        if not original_ends_with_newline and not fix:
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
