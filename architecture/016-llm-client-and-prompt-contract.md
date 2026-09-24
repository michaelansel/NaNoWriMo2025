# ADR-016: One LLM client and the prompt contract

## Status

Status: Accepted

## Context

Earlier AI code had one client per feature, prompts as Python strings (with a brace-escaping bug class), free-text JSON scraping, and paths where an exception or a truncated reply became "no issues". Inference now goes to an OpenAI-compatible gateway by default, with other OpenAI-compatible providers for local use, and reasoning models that can spend their whole token allowance thinking.

## Decision

`nanoif.llm` is the only code that talks to a model.

- **Client.** `LLMClient` on the `openai` SDK against any OpenAI-compatible endpoint. The network boundary is an injectable `Transport`, so tests never open a socket (`FakeLLM`, `RecordingLLM`, `ReplayLLM` in `nanoif.llm.fake`).
- **Profiles** (`nanoif.llm.profiles`, the only home for URLs, model ids and default limits): `exe` (default, gateway, no key), `fireworks` (local use only, key from the environment), `ollama` (concurrency forced to 1, prompt-mode JSON), `custom` (URL, key and model all from the environment). `NANOIF_LLM_PROFILE` selects one; every field has a `NANOIF_LLM_*` override. Bad configuration raises `LLMConfigError` before any call.
- **Structured output.** A call with a schema asks for `json_schema` strict mode; on a 400 that rejects the format it falls back once to `json_object` with the schema in the system prompt; `ollama` uses prompt mode. Output is validated with `jsonschema`. An invalid reply gets exactly one repair round (the client's own instruction in `nanoif/llm/templates/repair.md`, with the validation errors), then `LLMSchemaError`.
- **Typed errors, no default result.** `LLMTransportError` (network, HTTP status, empty choices), `LLMTruncatedError` (`finish_reason=length`), `LLMSchemaError`, `LLMBudgetExceeded`. Nothing in the package turns any of them into an empty findings list; callers mark the unit `error` (ADR-019).
- **Budget and accounting.** `NANOIF_LLM_MAX_TOKENS_PER_JOB` (default 2M) is checked before every send, including the fallback resend. Reasoning models get `max_tokens` of at least 8000 and `reasoning_effort` as an API parameter, never prompt text. Each call logs one JSON line (tokens, latency, attempts, USD); effective settings are logged once per job; `usage_summary()` feeds comment headers, check-run summaries and `ai-review.json`. Unknown prices report `usd_known: false`, not zero cost.
- **Prompts are files.** Each prompt is `nanoif/prompts/<name>.md` (Jinja, `system` and `user` blocks, story text between delimiters and declared to be data) with a sibling `<name>.schema.json` for its output. Python holds no prompt text. Few-shot examples use eval-story names only. A prompt change is measured with `nanoif ai eval` against `tests/eval/baselines/<profile>.json`.

## Consequences

### Positive

- Switching provider is an environment change; the eval baseline says whether quality held.
- Every failure mode has a name, and every caller has to decide what the writer sees.
- Prompt edits are reviewable diffs and cannot break Python string formatting.

### Negative

- The repair round and the fallback resend can double the cost of a bad call; the budget bounds it.
- Strict `json_schema` limits schema features to what providers accept.

## Alternatives Considered

1. **A provider-specific SDK**: locks the default out of local and gateway use.
2. **Retry until valid**: unbounded cost and latency; one repair then a visible error is enough.
3. **Prompts as Python constants**: the source of the brace bug and of prompt text drifting from schemas.

## References

- ADR-019 (`ai-review.json`), `.claude/rules/prompts.md`, `tests/llm/`, `tests/eval/`
