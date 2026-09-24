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
4. **Conflicts**: pairs of facts that disagree, with both quotes; deliberate ones collapsed under
   "Intentional mysteries".
5. **Freshness**: the commit and date the Bible was extracted from, and the passages changed
   since then that it has not read.

**Extraction** runs automatically after each merge to `main` and saves its result to
`ai/story-bible-cache.json` on `main`. Only passages whose text changed are re-read. The page is
rendered from that saved result on every build, with no AI call, so a pull request preview shows
the Bible as of `main` plus a banner naming the pull request's passages it has not read.

**Overrides** live in `story-overrides.txt` at the repository root, one directive per line,
`#` for comments. Using eval-story names:
```
alias: Tamsin Reeve = Old Tam, Tam
not-entity: the man who built the weir
pin: River Wardens = The River Wardens fly a green pennant | "the green pennant of the River Wardens" @ The crossing
intentional-conflict: c-widow-never-wife
```
Syntax errors in this file are reported by the structure check
([structure-check](structure-check.md)).

**For the Continuity Editor** the Bible provides a compact canon: per entity, a few facts with
stable ids, pinned facts first ([continuity-review](continuity-review.md)).

**On demand**: `/extract-story-bible` on a pull request (collaborators only) is a dry run that
posts a comment listing what would change; it commits nothing.

## Acceptance criteria
- AC-story-bible-1: With no saved extraction, the build still passes and `story-bible.html` shows a placeholder that says how many passages the story has.
- AC-story-bible-2: A saved extraction that exists but cannot be read fails the build, and no Story Bible page is written over the last good one.
- AC-story-bible-3: The page title carries the story title from `StoryTitle`, and the page shows the commit it was built from and when.
- AC-story-bible-4: Quotes and facts from the extraction are HTML-escaped on the page, so markup in them shows as text.
- AC-story-bible-5: The page has the sections Cast, Places, Items, Groups, World rules, Conflicts and Freshness, in that order. (verify: planned)
- AC-story-bible-6: Each Cast entry shows the canonical name, aliases, role, the number of passages the character appears in, and each fact with a verbatim quote and its passage name. (verify: planned)
- AC-story-bible-7: Extracted from the eval story, the Cast lists all 8 characters once each, with `Old Tam` and `Tam` as aliases of `Tamsin Reeve`. (verify: planned)
- AC-story-bible-8: Extracted from the eval story, Places, Items and Groups list the 4 locations, 3 items and 1 group, with `the old mill` as an alias of `Weir House`. (verify: planned)
- AC-story-bible-9: Extracted from the eval story, none of the distractor phrases `no one`, `the man` and `thirteen people` is an entity. (verify: planned)
- AC-story-bible-10: Extracted from the eval story, at least 20 of the 25 planted facts appear, and every fact shown has a quote found verbatim in its cited passage. (verify: planned)
- AC-story-bible-11: Extracted from the eval story, none of the 4 planted scene-state statements appears as a fact. (verify: planned)
- AC-story-bible-12: Extracted from the eval story, at least 5 of the 6 resolvable pronoun cases are attributed to the right character and both ambiguous cases are left unattributed. (verify: planned)
- AC-story-bible-13: Extracted from the eval story, Conflicts lists `c-tam-years` and `c-pip-age`, and `c-widow-never-wife` appears only under "Intentional mysteries". (verify: planned)
- AC-story-bible-14: An `alias:` override merges the named entities into one entry; a `not-entity:` override removes the entity; a `pin:` override shows the fact with its quote and passage even if extraction missed it. (verify: planned)
- AC-story-bible-15: The Freshness section shows the commit and date of the extraction and lists by name every passage whose text changed since then. (verify: planned)
- AC-story-bible-16: In a pull request preview, the page shows a banner naming the pull request's new or changed passages that the Bible has not read, and the Build comment states how many there are. (verify: planned)
- AC-story-bible-17: After a merge to `main`, extraction re-reads only passages whose text changed and commits `ai/story-bible-cache.json` to `main` only when it changed; it never commits to a pull request branch. (verify: planned)
- AC-story-bible-18: When extraction fails, the deploy still happens with the last good Bible, and the page states that the latest extraction failed and the date of the one shown. (verify: planned)
- AC-story-bible-19: `/extract-story-bible` from a collaborator on a pull request posts a comment listing what would change and commits nothing; from anyone else it starts no job. (verify: planned)
- AC-story-bible-20: Each fact keeps a stable id across extractions; a reworded fact keeps its id, and a retired id is never given to another fact. (verify: planned)
- AC-story-bible-21: A pinned fact is always among the facts the Continuity Editor checks a passage against when that passage mentions the pinned entity. (verify: planned)
- AC-story-bible-22: A full extraction of a story of up to 100 passages costs at most $1 at the default profile's prices. (verify: planned)

## Edge cases
- **No extraction yet** (a fresh story): the placeholder page; every landing link still works.
- **Saved extraction unreadable**: the build fails loudly rather than publishing a placeholder over
  real data (AC-story-bible-2).
- **Extraction fails after a merge**: the site deploys with the previous Bible and says so
  (AC-story-bible-18).
- **A passage is deleted**: its facts are retired, and their ids are not reused.
- **Overrides name an entity that does not exist**: the line has no effect; a later extraction
  that finds the entity applies it.
- **Two merges close together**: the second extraction starts from the first one's saved result.

## Soft goals
- A writer can answer "what have we said about this character?" from the page in under a minute.
- The Cast section is short enough to read in one sitting.

## Out of scope
- Variables, player-choice state, "what happens if the player does nothing", and timelines.
- Editing the Bible directly; corrections go through `story-overrides.txt`.
- Blocking merges on Bible conflicts.
