---
paths:
  - "nanoif/**/*.py"
  - "pyproject.toml"
---

# Python in `nanoif/`

- Python 3.11+. `ruff check` must be clean; `E722` (bare `except:`) is an error, not a warning.
- TDD: write the failing test in `tests/` first, then the minimal change, then refactor. Every bug fix starts with a test that reproduces it.
- Line length 100, type hints on every public function, Google-style docstrings (Args/Returns/Raises), imports grouped stdlib / third-party / local.
- `pathlib.Path` everywhere; resolve paths from an explicit argument or `Path(__file__)`, never from the cwd.
- Errors are typed and raised: `LLMTransportError`, `LLMTruncatedError`, `LLMSchemaError`, `LLMBudgetExceeded`, and their callers. No code path returns an empty or "no issues" result because something failed. A caught exception is re-raised, converted to a typed error, or turned into a visible `error` state on the unit it belongs to.
- No `except Exception` around cache or config loads; a corrupt file is an error the run reports, not an empty dict.
- One implementation per concern: one passage-header regex, one link parser, one story parser, one JSON-from-LLM parser. If you need a second, delete the first.
- JSON that crosses a process boundary goes through a file or stdin, never a shell heredoc. Artifacts are validated against `nanoif/schemas/` at write time.
- Subprocess calls (git, tweego) have a timeout and check the return code. Cache `git log` per file; never call git inside a per-path loop.
- Prompts are Jinja files under `nanoif/prompts/`; Python holds no prompt text. See `rules/prompts.md`.
- No print debugging to stderr in library code; the CLI decides what to show.
- Constants (`OLLAMA_MODEL`, URLs, model ids) live in `nanoif/llm/profiles.py`, nowhere else.
