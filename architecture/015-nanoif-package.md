# ADR-015: One installable package, `nanoif`

## Status

Status: Accepted
Supersedes: ADR-009, ADR-012

## Context

The tooling grew as scripts in `lib/`, `formats/`, `scripts/` and `services/` with six story parsers, several link regexes, a home-made test harness, shell heredocs passing JSON, and code that resolved paths against the current directory. CI relied on whatever Python packages the runner image had. ADR-012's rule that formats consume shared core artifacts and never each other was right; its layout and its "webhook AI" pipeline category are gone.

## Decision

All Python lives in one package, `nanoif/`, installed with `pip install -e ".[dev]"` from `pyproject.toml` (Python 3.11+; runtime deps `jinja2`, `openai`, `jsonschema`; dev deps `pytest`, `ruff`). One console script, `nanoif`.

- **One implementation per concern.** `nanoif.twee` owns the one passage-header regex (`files`), the one link parser (`links`) and the one story parser (`parse`, from Tweego HTML or raw Twee). `nanoif.git.service` is the one place that runs `git`. `nanoif.llm.schema` is the one JSON-from-LLM parser. A second implementation means deleting the first.
- **Core artifacts, independent formats** (carried from ADR-012). `nanoif build core` writes `story_graph.json` and `passages_deduplicated.json`; each format (`nanoif.formats.allpaths`, `metrics`, `passages`, `story_bible`) reads those and never another format's output.
- **Schema-validated artifacts.** Every JSON artifact that crosses a process or job boundary has a schema in `nanoif/schemas/artifacts/` and is validated when written (`write_artifact`) and when read (`load_artifact`). A missing or non-conforming artifact is a typed error, never an empty default.
- **Paths from `--repo`.** Every command takes `--repo` (or an explicit path) and derives `src/`, `lib/artifacts/`, `dist/` and state files from it (`nanoif.build.paths.ProjectPaths`). Nothing resolves against the current directory.
- **Typed errors.** Package errors derive from `nanoif.errors.NanoifError`; LLM errors derive from `nanoif.llm.errors.LLMError` (ADR-016). The CLI prints either as one `error:` line and exits 1.
- **Thin wrappers.** `scripts/build-*.sh` only call tweego and `nanoif`; they hold no logic. Workflows call `nanoif` directly where they can.
- **Required checks.** `ruff check nanoif tests` (with E722) and `pytest` run in CI on every PR. Tests are plain pytest; model calls use `nanoif.llm.fake`.

## Consequences

### Positive

- A bug in parsing or link handling is fixed once, and every output agrees.
- A malformed artifact stops the build at the step that produced it, with its path and the first schema violation.
- The same commands run locally, on hosted runners and on the exe runner.

### Negative

- Every change to an artifact's shape is a schema change as well as a code change.
- Legacy trees (`services/`, `lib/`, old `scripts/`) stay excluded from lint until they are deleted.

## Alternatives Considered

1. **Targeted fixes in the old layout**: cheaper this month, but keeps the parser duplication that produced disagreeing outputs.
2. **Several packages (core, build, ai)**: more boundaries than one small team needs.
3. **Validate artifacts only in tests**: a bad artifact would still reach the next job silently.

## References

- ADR-016 (LLM client), ADR-017 (AllPaths and categorization), `pyproject.toml`, `.claude/rules/python.md`
