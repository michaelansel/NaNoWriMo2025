# Story Bible

**Status**: building

## User problem
Several writers build one world across dozens of branching passages. Nobody can hold every name,
relationship and rule in their head, and the facts that matter are scattered across files other
people wrote. A reference is only useful if it is short, correct and current: a list padded with
"characters" like *no one* or *thirteen people*, or hundreds of restated scene details, gets
ignored. The Continuity Editor needs the same reference, in compact form, to check a passage
against facts established on other branches.

## User stories
- As a writer, I want one page listing the cast, places, items, groups and world rules, each fact
  with the quote and passage it came from, so that I can check canon before I write.
- As a writer, I want the page to say how current it is and which passages it has not read yet,
  so that I know when not to trust it.
- As a writer, I want to correct the Bible (merge two names, drop a false entity, pin a fact,
  mark a deliberate mystery) by editing one text file in the web UI.
- As a writer, I want contradictions between established facts listed, with deliberate
  mysteries kept apart, so that I can tell mistakes from intent.

## Behavior
**Page** (`story-bible.html`, linked from the landing page), sections in this order:
1. **Cast**: one entry per character: canonical name, aliases, role, number of passages it
   appears in, and its established facts, each with a verbatim quote and the passage name.
   Momentary scene state ("the stew had gone cold") is not a fact.
2. **Places**, **Items**, **Groups**: named or recurring ones only, same entry shape.
3. **World rules**: facts true of the world rather than one entity (for example, no crossing
   without a lit lantern).
4. **Conflicts**: pairs of facts that disagree, each with its id (`c-...`) and both quotes.
5. **Intentional mysteries**: conflicts the writers marked as deliberate, under their id or label.
6. **Freshness**: the commit and date the Bible was extracted from; every passage it has not read
   in its current text (new, changed, or failed to extract); passages it read that no longer
   exist; and, when the latest extraction did not complete, a line saying so with the date of the
   extraction shown.

**Extraction** runs automatically after each merge to `main` and saves its result to
`ai/story-bible-cache.json` on `main`. Only passages whose text changed are re-read; when none
did, no AI is called. Every fact keeps a stable id; a fact that is gone is retired and its id is
never reused. The page is rendered from the saved result on every build, with no AI call, so a
pull request preview shows the Bible as of `main`: its Freshness section names the pull request's
new or changed passages, and the Build comment says how many passages the Bible has not read.

**Overrides** live in `story-overrides.txt` at the repository root, one directive per line,
`#` for comments. Using eval-story names:
```
alias: Tamsin Reeve = Old Tam, Tam
not-entity: the man who built the weir
pin: River Wardens = The River Wardens fly a green pennant | "the green pennant of the River Wardens" @ The crossing
intentional-conflict: c-widow-never-wife = Widow Kestle | never anyone's wife
```
`intentional-conflict:` has two forms: an id copied from the Conflicts section
(`intentional-conflict: c-<id>`), or a label with an entity and a fragment of one quote, as above.
A pinned fact whose quote is not in the named passage is still pinned, flagged `quote not found`.
Override edits show in the next build, without a new extraction. Syntax errors in this file are
reported by the structure check ([structure-check](structure-check.md)).

**For the Continuity Editor** the Bible provides a compact canon: per entity, a few facts with
stable ids, pinned facts first ([continuity-review](continuity-review.md)).

**On demand**: `/extract-story-bible` on a pull request (collaborators only) is a dry run of the
pull request merged with `main`. It posts one comment headed "dry run: nothing was saved" listing
what would change and what the run cost, or "did not run" with the reason; it commits nothing.

## Acceptance criteria
- AC-story-bible-1: With no saved extraction, the build still passes and `story-bible.html` shows a placeholder that says how many passages the story has.
- AC-story-bible-2: A saved extraction that exists but is unreadable, is not the current version, fails its schema, or holds a reference that points nowhere fails the build, and no Story Bible page is written over the last good one; an extraction started from it fails and saves nothing.
- AC-story-bible-3: The page title carries the story title from `StoryTitle`, and the page shows the commit it was built from and when.
- AC-story-bible-4: Quotes and facts from the extraction are HTML-escaped on the page, so markup in them shows as text.
- AC-story-bible-5: The page has the sections Cast, Places, Items, Groups, World rules, Conflicts, Intentional mysteries and Freshness, in that order.
- AC-story-bible-6: Each Cast entry shows the canonical name, aliases, role, the number of passages the character appears in, and each fact with a verbatim quote and its passage name.
- AC-story-bible-7: Extracted from the eval story, the Cast lists all 8 characters once each, with `Old Tam` and `Tam` as aliases of `Tamsin Reeve`. (verify: workflow)
- AC-story-bible-8: Extracted from the eval story, Places, Items and Groups list the 4 locations, 3 items and 1 group, with `the old mill` as an alias of `Weir House`. (verify: workflow)
- AC-story-bible-9: Extracted from the eval story, none of the distractor phrases `no one`, `the man` and `thirteen people` is an entity. (verify: workflow)
- AC-story-bible-10: Extracted from the eval story, at least 20 of the 25 planted facts appear, and every extracted fact shown has a quote found verbatim in its cited passage. (verify: workflow)
- AC-story-bible-11: Extracted from the eval story, none of the 4 planted scene-state statements appears as a fact. (verify: workflow)
- AC-story-bible-12: Extracted from the eval story, at least 5 of the 6 resolvable pronoun cases are attributed to the right character and both ambiguous cases are left unattributed. (verify: workflow)
- AC-story-bible-13: Extracted from the eval story with its `story-overrides.txt`, Conflicts has an entry matching each of `c-tam-years` and `c-pip-age` by their truth quotes, and `c-widow-never-wife` appears only under Intentional mysteries. (verify: workflow)
- AC-story-bible-14: An `alias:` override merges every entity whose name or alias matches into one entry under the canonical name; a `not-entity:` override removes the entity whose name or alias matches; a `pin:` override shows the fact with its quote and passage even if extraction missed it; each takes effect in the next build without a new extraction.
- AC-story-bible-15: The Freshness section shows the commit and date of the extraction, and lists by name every passage the extraction has not read in its current text (new, changed, or failed to extract) and every passage it read that no longer exists.
- AC-story-bible-16: The Build comment states how many passages the Story Bible has not read in their current text, and in a pull request preview the Freshness section names the pull request's new or changed passages among them.
- AC-story-bible-17: Extraction sends a passage to the model only when its text differs from the saved extraction, makes no model call when no passage changed, and saves the extraction only when the set of passages or their texts changed.
- AC-story-bible-18: When the latest extraction did not succeed (failed, cancelled, skipped, or stopped by the spend cap), the page says the latest extraction did not complete and gives the date of the extraction it shows.
- AC-story-bible-19: `/extract-story-bible` from an owner, member or collaborator on a pull request runs a dry run of the pull request merged with `main` and commits nothing; from anyone else it starts no job and spends nothing; when the AI runner is unavailable or the run fails, its job fails. (verify: workflow)
- AC-story-bible-20: Each fact keeps its id across extractions: a fact re-extracted from its changed passage with the same quote or a reworded claim keeps its id, the facts of a merged entity keep theirs, a fact no longer found or whose passage was deleted is retired, and a retired id is never given to another fact.
- AC-story-bible-21: A pinned fact is always among the facts the Continuity Editor checks a passage against when that passage mentions the pinned entity.
- AC-story-bible-22: A full extraction of a story of up to 100 passages costs at most $1 at the default profile's prices. (verify: workflow)
- AC-story-bible-23: An extracted fact whose quote is not found in its passage, a fact that is momentary scene state, and an entity whose name starts with a quantifier or number word (`no one`, `thirteen people`) never reach the page or the canon, and the saved extraction records per passage how many of each were dropped.
- AC-story-bible-24: A `pin:` whose quote is not found in the named passage is still shown and still pinned, flagged `quote not found`.
- AC-story-bible-25: `intentional-conflict: c-<id>` moves the conflict with that id from Conflicts to Intentional mysteries; `intentional-conflict: <label> = <entity> | <quote fragment>` lists the label under Intentional mysteries and moves there every conflict on that entity with a quote containing the fragment.
- AC-story-bible-26: An `intentional-conflict:` line that matches no conflict changes nothing and is listed on the page as `unmatched`.
- AC-story-bible-27: An `alias:` or `not-entity:` line that matches no entity the Bible knows is listed on the page as `unmatched`. (verify: planned)
- AC-story-bible-28: The canon offered for a passage never includes facts drawn from that passage or from a passage whose text changed since the extraction.
- AC-story-bible-29: Only the extraction job on `main` commits the saved extraction, as a commit of `ai/story-bible-cache.json` alone to `main`; it never runs for a pull request, and nothing commits to a pull request branch. (verify: workflow)
- AC-story-bible-30: When extraction fails or is skipped after a merge, the site still deploys with the latest saved Bible. (verify: workflow)
- AC-story-bible-31: The `/extract-story-bible` result is one comment per pull request, found by its `<!-- nano:bible -->` marker and edited in place, headed "dry run: nothing was saved" and listing the entities, facts and conflicts that would be added, changed or retired and what the run cost; when the run did not happen or failed, it says "did not run" with the reason and shows no earlier result.
- AC-story-bible-32: When this month's AI spend has reached the cap, or the extraction's estimate would pass it, extraction makes no model call and saves nothing; a run stopped by the cap part-way saves nothing; and `/extract-story-bible` says "did not run" with the reason of AC-continuity-review-31.

## Edge cases
- **No extraction yet** (a fresh story): the placeholder page; every landing link still works.
- **Saved extraction unreadable**: the build fails loudly rather than publishing a placeholder over
  real data (AC-story-bible-2).
- **Extraction fails after a merge**, or the AI runner is offline: the site deploys with the
  latest saved Bible and says the latest extraction did not complete (AC-story-bible-18,
  AC-story-bible-30).
- **Extraction fails for some passages only**: what was read is saved; the failed passages are
  listed in Freshness as not read, and the extraction job stays red until they succeed.
- **Monthly AI spend cap reached**: no extraction runs and nothing is saved; the page says the
  latest extraction did not complete (AC-story-bible-32).
- **A passage is deleted**: its facts are retired, their ids are not reused, and Freshness lists
  it until the next extraction.
- **Overrides name an entity or conflict that does not exist**: the line has no effect; an
  `intentional-conflict:` line is listed as `unmatched` (AC-story-bible-26). A later extraction
  that finds the entity applies it.
- **Two merges close together**: the second extraction starts from the first one's saved result.
- **A deliberate mystery is also flagged by the Continuity Editor**: findings on its facts are
  suppressed ([continuity-review](continuity-review.md), AC-continuity-review-14).

## Soft goals
- A writer can answer "what have we said about this character?" from the page in under a minute.
- The Cast section is short enough to read in one sitting.

## Out of scope
- Variables, player-choice state, "what happens if the player does nothing", and timelines.
- Editing the Bible directly; corrections go through `story-overrides.txt`.
- Blocking merges on Bible conflicts.
