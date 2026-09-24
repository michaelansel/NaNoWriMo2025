#!/usr/bin/env bash
# SessionStart: report whether nanoif is importable and enable the intent commit gate.
# Never fails the session.
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
if command -v nanoif >/dev/null 2>&1; then
  echo "nanoif: $(nanoif --version 2>/dev/null || echo installed)"
else
  echo 'nanoif not installed; run: pip install -e ".[dev]"  (hook skipped)'
fi
if [ -x "$root/.githooks/commit-msg" ]; then
  if [ "$(git -C "$root" config --get core.hooksPath 2>/dev/null)" != ".githooks" ]; then
    git -C "$root" config core.hooksPath .githooks && echo "intent gate: enabled (core.hooksPath=.githooks)"
  else
    echo "intent gate: enabled"
  fi
fi
exit 0
