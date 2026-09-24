---
name: eval-prompts
description: Run the prompt eval against the committed baseline and report the delta. Use after any change under nanoif/prompts/, nanoif/schemas/, or nanoif/llm/, and before a commit typed prompt.
allowed-tools: Bash(nanoif ai eval*), Bash(pytest*), Read, Grep, Glob
---

# Evaluate prompts

1. Run `pytest tests/test_fixture_integrity.py -q`. If it fails, stop: the fixture and its truth disagree, and no eval result is meaningful.
2. Run `nanoif ai eval --profile "${NANOIF_LLM_PROFILE:-exe}" --json > /tmp/eval.json`. If the command is missing or the gateway is unreachable, report "eval could not run: <reason>" and stop. Never describe a prompt change as verified when the eval did not run.
3. Read `tests/eval/baselines/<profile>.json` and compare every metric.

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
