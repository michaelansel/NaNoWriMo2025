---
paths:
  - "nanoif/prompts/**"
  - "nanoif/schemas/**"
  - "nanoif/llm/**"
---

# Prompts, schemas, and the LLM client

- Every prompt is a Jinja file `nanoif/prompts/<name>.md` with a sibling `nanoif/prompts/<name>.schema.json` (artifact schemas live in `nanoif/schemas/`). Write the schema first; a hook refuses a prompt without one.
- System and user content are split with explicit delimiters; passage text is data, never instructions. The schema constrains the output; the code verifies every quote against the source before a finding is reported.
- Every finding cites two quotes with passage names. A finding whose quote is not found in the text goes to `unverified[]`, never to the reader.
- No template contains the phrases "no issues", "perfect", "flawless", or any canned all-clear. An empty findings list is the only all-clear, and only after the call succeeded.
- Few-shot examples use names from `tests/fixtures/eval-story/` only.
- `reasoning_effort` is an API parameter, never a line in the prompt. `max_tokens` is at least 8000 for reasoning models.
- Canon pack sent to a prompt stays under 8k tokens: at most 6 facts per entity, no `state` facts, quote-less form. Retrieval is a word-boundary alias match over the passage under review.
- Severity is computed by code from finding type and path position, not taken from the model.
- Change the prompt, run `/eval-prompts`, commit with `prompt:` and the eval delta in the body. A metric below baseline needs a written reason in the PR.
- The client never returns a default result: transport, truncation (`finish_reason=length`), schema failure after one repair round, and budget exhaustion each raise their typed error.
- `json_schema` strict mode first; `json_object` fallback on a 400; prompt-mode JSON only for the `ollama` profile. Log effective parameters once per job.
- Every call writes one JSON log line with tokens and USD; `usage_summary()` feeds the comment header and step summary.
