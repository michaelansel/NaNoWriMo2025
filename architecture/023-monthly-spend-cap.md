# ADR-023: Monthly AI spend cap and spend ledger

Status: Accepted
Extends: ADR-016

## Context

The exe.dev gateway's token allocation is shared with the owner's other VMs, and its own per-VM limits are unknown. The owner wants this project to stop itself at a fixed monthly amount. ADR-016's `NANOIF_LLM_MAX_TOKENS_PER_JOB` bounds one process; nothing bounds a month of reviews, re-checks, extractions and evals. All paid inference in CI runs on the one `exe` runner VM, whose runner user's home directory persists across jobs; there is no hosted fallback key (ADR-014).

## Decision

`nanoif.llm` enforces a self-imposed monthly cap on *estimated list-price* spend, recorded in a per-machine ledger. It is not the provider's bill.

- **Ledger** (`nanoif/llm/ledger.py`, the only code that reads or writes it). One append-only JSONL file per UTC month, `<dir>/YYYY-MM.jsonl`, one line per transport response or charged failure: `{at, month, profile, model, prompt_tokens, completion_tokens, usd, usd_known, estimated, tag, run}` (`run` from `GITHUB_RUN_ID`, else `null`). Each line is validated against `nanoif/schemas/artifacts/spend_ledger_line.schema.json` when written and when read. Appends take a `threading.Lock` and `fcntl.flock(LOCK_EX)` and write one complete line. Reads take `LOCK_SH`. The client reads the current month's file on first use, then reads only the bytes appended since its last offset before each check, so another process's spend is counted.
- **Directory.** `NANOIF_LLM_LEDGER_DIR`. When it is set, the directory must already exist (`LLMConfigError` otherwise), so a lost or moved directory fails loudly instead of starting again at zero. When it is unset, the default `$XDG_STATE_HOME/nanoif/spend` (or `~/.local/state/nanoif/spend`) is created. `deploy/exe/setup.sh` creates the directory and writes `NANOIF_LLM_LEDGER_DIR` into the runner's `.env`. The ledger never lives in the checkout or under `ai/`.
- **Cap.** `NANOIF_LLM_MONTHLY_USD`, default `10` (`DEFAULT_MONTHLY_USD` in `profiles.py`), is parsed in `Settings`. It accepts a non-negative number, `0` (no paid inference at all: a kill switch), or the exact word `off`. Anything else, including a negative number, raises `LLMConfigError`. An empty value means the default. All three workflows set `NANOIF_LLM_MONTHLY_USD: ${{ vars.LLM_MONTHLY_USD }}` in their top-level `env:`, so the owner changes it in repository settings. `off` is logged in `llm_config`, reported as `month_cap_usd: null`, and printed in every step summary.
- **Refuse before, never overshoot knowingly.** `_check_budget` also checks spend before every send (first send, fallback resend, repair round). The pessimistic cost of a call is its prompt estimate at the input rate plus `max_tokens` at the output rate. The client refuses when month-to-date plus in-flight reservations plus that cost is more than the cap. The reservation is held under the client lock from the check until the response is recorded, so concurrent threads cannot jointly overshoot. The refusal is `LLMSpendCapReached`.
- **What is charged.** A response is charged its reported usage, including truncated and schema-invalid replies. A transport failure with no status or a 5xx is charged its pessimistic cost with `estimated: true`, because the provider may have generated tokens. A 4xx, or a call refused by either cap, is not charged. Unknown models are charged at `UNPRICED_CAP_RATE` = $1.00/M input, $4.00/M output (in `pricing.py`, above every priced row) with `usd_known: false`. Reports still say "cost unknown" for them (ADR-016).
- **Halting errors.** A new base class `LLMRunHalted(LLMError)` has a `reason: str` attribute. `LLMBudgetExceeded`, `LLMSpendCapReached` and `LLMLedgerError` (unreadable or invalid ledger line, named `path:line`; a failed append) are subclasses. `LLMSpendCapReached` is not a subclass of `LLMBudgetExceeded`, whose attributes are token counts. The review runner catches `LLMRunHalted`, stops, and marks the remaining units `skipped` with `exc.reason`, replacing the fixed `token budget exhausted` string. A failed append does not discard the result it follows; it halts the client, so the next send raises `LLMLedgerError`. A corrupt ledger fails closed until the line is fixed on the VM (runbook `docs/exe-runner.md`).
- **Fail fast.** The `Completer` protocol gains `check_spend(estimate_usd: float = 0.0)`, which raises `LLMRunHalted`. `review()` calls it once before planning. On a halt, every editor is `skipped` with the reason, `ai-review.json` is still written, and the CLI exits 1, so the reporter publishes "unavailable" and the check run fails. The reason reads `monthly AI spend cap reached: $X.XX of $C.CC in YYYY-MM (resets YYYY-MM-01 UTC)`. `/check-continuity all` calls `check_spend(<its estimate>)` before posting the estimate and refuses with the same reason. A bible extraction that halts writes no cache and exits non-zero; deploy uses the previous cache (ADR-020).
- **Visibility.** `usage_summary()` gains `month` (`YYYY-MM`), `month_usd`, `month_usd_known`, `month_cap_usd` (`null` when off) and `month_cap_reached`. These are optional properties in `ai_review.schema.json`, and readers treat a missing key as unknown. `nanoif ai review` and `nanoif ai eval` print `monthly AI spend: $X.XX of $C.CC in YYYY-MM` for the step summary. When `month_cap_reached` is true, the reporter states the reset date instead of suggesting a retry.

## Consequences

### Positive

- An unpriced model, a runaway loop, a concurrent burst or a lost ledger directory cannot spend past the cap without a visible failure.
- Reaching the cap produces the same "did not run, not a pass" result on the PR as any other outage, and names the reset date.
- The owner can raise, lower, zero or disable the cap without SSH.

### Negative

- It measures list price from our table, not the gateway's allocation accounting. The two may differ, and the gateway can still refuse earlier.
- SDK-internal retries (`NANOIF_LLM_MAX_RETRIES`) are invisible to the client and charged once. Rebuilding the VM or deleting the directory resets the month. A second machine with the same gateway keeps its own ledger.
- A corrupt ledger line stops all AI work until someone fixes it on the VM. That is loud but manual.
- The pessimistic estimate refuses the last few cents of the month.

## Alternatives Considered

1. **Allow one call to overshoot**: simpler, but with 4 concurrent calls and repair rounds, "one" is not one. Refuse-before costs cents.
2. **Ledger under `ai/` committed by Actions**: adds a fourth `contents: write` job and a commit per review, and it still misses local use.
3. **Subclass `LLMBudgetExceeded`**: would put USD in token-typed fields and keep the runner's hard-coded reason.
4. **Charge unknown models zero**: an unpriced model would bypass the cap.
5. **Treat a corrupt ledger as empty**: the silent reset this ADR exists to prevent.

## References

- ADR-014 (exe runner), ADR-016 (client, per-job budget), ADR-020 (bible extraction), ADR-022 (`ai-review.json`, editor status)
- `nanoif/llm/{ledger,client,profiles,pricing,errors}.py`, `nanoif/review/runner.py`, `deploy/exe/setup.sh`, `docs/exe-runner.md`
