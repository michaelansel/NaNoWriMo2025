#!/usr/bin/env bash
# SessionStart: say whether the nanoif package is importable. Never fails.
if command -v nanoif >/dev/null 2>&1; then
  echo "nanoif: $(nanoif --version 2>/dev/null || echo installed)"
else
  echo 'nanoif not installed; run: pip install -e ".[dev]"  (hook skipped)'
fi
exit 0
