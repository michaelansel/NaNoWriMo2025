# ADR-020: Story Bible v2: extract, resolve, merge, pack

## Status

Status: Proposed
Would supersede ADR-010 once accepted.

## Context

The first Story Bible (ADR-010) extracted facts per path in a webhook, deduplicated by exact text, and listed noise as characters while hundreds of "setting" facts restated each other. The proposals that followed (per-passage chunked extraction, entity-first extraction, semantic aggregation) each fixed one stage. The Continuity Editor needs a small, stable canon to check against, and writers need a page they trust and a way to correct it without editing JSON.

## Decision

`nanoif/bible/` builds the bible in four stages, run by `bible-extract` on the exe runner after each merge to main (ADR-014) and by `nanoif bible extract --incremental` locally.

- **Extract** per passage, cached by `content_hash`: `{summary, entities[{name, type, aliases, facts[{claim, evidence_quote, kind}]}]}`. Only passages whose hash is not in the cache are sent.
- **Resolve** aliases: deterministic normalization, then one batched model pass that proposes merges with confidence; `story-overrides.txt` wins over both.
- **Merge** per entity: the model returns input fact indices and, for existing facts, `keep|reword|retire` plus `new`; code attaches evidence and checks every index appears exactly once, else the entity keeps its unmerged facts with `merge_status: fallback`.
- **Assemble** deterministically: canon, conflicts and entity index. Entity types are `character`, `location`, `item`, `group`, `world`. No variables, zero-action state or timeline.
- **Stable fact ids** `<entity>#<n>` are never reused; retired facts are tombstoned so dismissals and conflicts keep pointing at something.
- **Overrides**: `story-overrides.txt` at the repository root, writer-editable in the web UI, one `directive: payload` per line: `alias:`, `not-entity:`, `pin:`, `intentional-conflict:`. Its syntax is checked by `nanoif check structure` (ADR-018); the bible applies its meaning.
- **Cache** `ai/story-bible-cache.json`: `version: 2`, keys `passages`, `resolution`, `entities`, sorted-key JSON, committed to main only by `bible-extract`. No v1 migration. A cache that exists but cannot be read fails the job; a missing cache renders the placeholder.
- **Canon pack** `dist/canon-pack.json`, built from the cache and overrides with no model: per entity at most 6 facts (pinned, then cited, then recent), no `state` facts, prompt form without quotes, an alias index for word-boundary retrieval over the passage under review, and conflicts with `intentional`. Quotes are re-attached in reports.
- **Freshness**: the PR build lists passages whose hash is not in the cache; the bible page, the Build comment and the Continuity header say so.

## Consequences

### Positive

- One entity per real character, with evidence for every fact and conflicts shown, not merged away.
- Canon is data with history in git, rendered with no model and diffable per merge.
- Writers correct the bible in a text file the build checks.

### Negative

- Three model stages cost more than one; per-passage caching keeps daily cost to new passages.
- Stable ids and tombstones make the cache format the hardest contract to change.
- If extraction lags, the Continuity Editor runs with an empty canon slice for new passages and says so.

## Alternatives Considered

1. **Keep v1 and add semantic dedupe**: fixes duplicates but not noise entities or unstable facts.
2. **Rebuild the bible from scratch every merge**: fact ids would churn and dismissals could not reference them.
3. **Cache in the Actions cache or a data branch**: loses reviewable history; a data branch stays the fallback if main is protected.

## References

- ADR-010, ADR-014, ADR-018, ADR-019; `nanoif/check/overrides.py`; `tests/fixtures/eval-story/truth.json`
