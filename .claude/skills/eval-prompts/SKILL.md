---
name: eval-prompts
description: Run the prompt eval against the committed baseline and report the delta. Use after any change under nanoif/prompts/, nanoif/schemas/, or nanoif/llm/, and before a commit typed prompt.
allowed-tools: Bash(nanoif ai eval*), Bash(pytest*), Read, Grep, Glob
---

# Evaluate prompts

1. Run `pytest tests/test_fixture_integrity.py -q`. If it fails, stop: the fixture and its truth disagree, and no eval result is meaningful.
2. Run `nanoif ai eval --repo . --baseline tests/eval/baselines/<profile>.json` (omit `--baseline` if that file does not exist yet), where `<profile>` is `$NANOIF_LLM_PROFILE` or `exe`. It writes `dist/eval-results.json` and `.md` and exits 0 pass, 1 below threshold or baseline, 2 could not run. On exit 2, or if the gateway is unreachable, report "eval could not run: <reason>" and stop. Never describe a prompt change as verified when the eval did not run. From outside the exe VM, run it on the runner instead: Actions, AI maintenance, task `eval`.
3. Compare every metric in `dist/eval-results.json` with the baseline.

## Acceptance table

| Metric | Threshold |
|---|---|
| Cast recall | 8 of 8 characters |
| Fact recall | at least 20 of 25 planted facts |
| Evidence | 100% of reported facts carry a quote found in the source |
| Pronoun resolution | at least 5 of 6 cases |
| Contradictions | 2 of 3 planted contradictions reported; the intentional one suppressed |
| Clean-path false positives | at most 1 finding across the clean paths |
| Regression fixtures | every 2025 false-positive fixture still produces no finding |
| Cost | full extraction under $1 on the `exe` profile |

## Report

Print a table with baseline, current, and delta for every metric. A regression is any metric below its baseline, not just below the threshold. For each regression, name the prompt or schema line most likely responsible.

If everything is at or above baseline and you intend to commit, write the new numbers to the baseline file in the same commit and quote the delta in the commit body under a `prompt:` subject.
