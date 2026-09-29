# ADR-024: Intentional mysteries mark facts, and the canon pack carries one suppression map

## Status

Status: Accepted
Supersedes: ADR-020 in part (the label form of `intentional-conflict:` and how the canon pack marks intentional facts; the rest of ADR-020 stands)

## Context

Under ADR-020, `intentional-conflict: <label> = <entity> | <quote fragment>` only moves conflicts the reconcile model detected into Intentional mysteries. The model rarely detects a contradiction inside one passage, such as the eval story's widow who says she was never anyone's wife, so the writer's line is listed as `unmatched` and the Continuity Editor keeps flagging the planted mystery when it cites that fact from other passages.

The canon pack marks intentional facts only through `conflicts[]` entries with `intentional: true`. Each entry is a detected pair (`fact_ids` has exactly 2 items), and `select_canon` derives `CanonSlice.intentional` from them.

## Decision

1. **Assemble.** A label line also matches every visible fact of its entity (facts, pins and rules as the page shows them, after `alias:` and `not-entity:`) whose quote contains the fragment. Matching uses the same `normalize_text(...).casefold()` containment that already matches conflicts. Facts already in a conflict matched by any line are left out. A fact belongs to at most one mystery: lines are applied in file order, and the first line wins. `Mystery` gains `facts: tuple[BibleFact, ...] = ()`. A line is `unmatched` only when it matches no conflict and no fact. `Bible.intentional_facts()` returns fact id to label for both the conflict facts and these facts. It is the only code that decides which facts are intentional.
2. **`story_bible` artifact.** Each `intentional_mysteries[]` item gains the required `facts` (items are the existing `fact` definition). The page lists these facts under the mystery's label, so the writer can see everything a fragment silenced.
3. **`canon_pack` artifact.** The pack gains the required top-level `intentional_facts: {<fact_id>: <label>}`, written from `Bible.intentional_facts()` unchanged. `select_canon` builds `CanonSlice.intentional` from this map alone, filtered to the facts it offers. Its derivation from `conflicts[]` is deleted rather than kept beside the map. `conflicts[]` is unchanged: each entry is still exactly one detected pair of fact ids, and `intentional` and `label` stay as descriptive fields. `version` stays 1. The producer and the consumer are always the same code in the same workflow run, and a pack without the key fails validation. A missing key is an error, never an empty map.
4. **Eval.** `nanoif ai eval` passes each fact of a mystery to the scorer as a `declared` entry with its quote.
   - Declared entries never count toward conflict recall, conflict precision or `reported`. Those numbers still measure only what the reconcile model detected.
   - `intentional_flagged` follows AC-story-bible-13. The intentional contradiction counts as flagged when two things hold:
     - a detected conflict or a declared fact under its label has a quote that overlaps one of its truth quotes;
     - no conflict that is not marked intentional overlaps both of its truth quotes.
   - Overlap is judged on quotes. An entry without a quote never counts.
   - This still tests extraction: a declared fact exists only when the model produced a verified quote that contains the fragment.
5. **Unchanged:** `ai/story-bible-cache.json` and its schema, and the reporter's suppression reason `intentional-conflict:<label>` (ADR-022).

## Consequences

### Positive

- A writer's declared mystery takes effect even when the model never paired the facts.
- The map is the pack's one home for "which facts are intentional", and `conflicts[]` keeps its pair invariant, so a malformed detected conflict still fails validation.

### Negative

- A short fragment such as `she` marks every fact of the entity whose quote contains it, and the Continuity Editor's findings on those facts go to `suppressed`. This is visible (the facts are listed under the label, and each suppressed finding gives its reason), but it is quiet.
- Only findings that cite a marked fact as canon are suppressed. Facts from the passage under review are never offered to it (ADR-020), so a contradiction the editor finds inside that passage has no canon fact id and is still shown. The eval criterion that the widow's mystery is never reported is the measure of whether this is enough.
- `intentional_flagged` no longer shows whether the model detected the planted contradiction. It shows that the fact was extracted and the writer's line took effect. No metric measures within-passage conflict detection.
- A marked fact whose quote is reworded on re-extraction can stop matching. The line then shows as `unmatched` on the next build.

## Alternatives Considered

1. **Emit a mystery as a `conflicts[]` entry with `id` = label and 1..n `fact_ids`** (needs no reader change). Rejected because it relaxes `fact_ids` from exactly 2 to at least 1, so a one-fact detected conflict (a bug) would pass validation. It would also put writer labels in the conflict-id namespace, and the eval's label `c-widow-never-wife` is already shaped like a conflict id.
2. **A map holding only the fact-only matches, merged with `conflicts[]` by the reader.** Rejected because it would leave two sources of the same answer and two readers of it.
3. **Persist the matches in the cache.** Rejected because overrides apply at assemble time on every build (ADR-020), and the cache is the most expensive contract to change.

## References

- ADR-020, ADR-022
- `features/story-bible.md`, `features/continuity-review.md`, `tests/fixtures/eval-story/story-overrides.txt`
