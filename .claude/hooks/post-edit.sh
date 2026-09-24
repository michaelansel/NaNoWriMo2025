#!/usr/bin/env bash
# PostToolUse Edit|Write: run the fast check that matches the edited path.
# A missing tool prints a visible "hook skipped" line and exits 0.
# A real failure prints the tool output on stderr and exits 2 so Claude sees it.
set -u
input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -n "$file" ] || exit 0
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
rel="${file#"$root"/}"
skip() { echo "hook skipped: $1"; exit 0; }
fail() { printf '%s\n%s\n' "$1" "$2" | tail -60 >&2; exit 2; }

case "$rel" in
  nanoif/*.py|tests/*.py|pyproject.toml)
    command -v ruff   >/dev/null 2>&1 || skip "ruff not installed (pip install -e \".[dev]\")"
    command -v pytest >/dev/null 2>&1 || skip "pytest not installed (pip install -e \".[dev]\")"
    if [ "$rel" != pyproject.toml ]; then
      out=$(ruff check "$file" 2>&1) || fail "ruff check $rel failed:" "$out"
    fi
    [ -d "$root/tests" ] || skip "no tests/ directory yet"
    out=$(cd "$root" && pytest -q -x -p no:cacheprovider -m "not slow" tests 2>&1) || fail "pytest failed after editing $rel:" "$out"
    echo "ruff + pytest ok ($rel)"
    ;;
  src/*.twee)
    command -v nanoif >/dev/null 2>&1 || skip "nanoif not installed; lint/check not run for $rel"
    out=$(cd "$root" && nanoif lint "$file" 2>&1) || fail "nanoif lint $rel reported:" "$out"
    out=$(cd "$root" && nanoif check structure src/ 2>&1) || fail "nanoif check structure reported:" "$out"
    echo "nanoif lint + check ok ($rel)"
    ;;
  .github/workflows/*.yml|.github/workflows/*.yaml)
    command -v actionlint >/dev/null 2>&1 || skip "actionlint not installed; $rel not linted"
    out=$(actionlint "$file" 2>&1) || fail "actionlint $rel failed:" "$out"
    echo "actionlint ok ($rel)"
    ;;
esac
exit 0
