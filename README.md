# NaNoWriMo interactive fiction

A branching story written together during NaNoWriMo. Writers add Twee passages from the GitHub
web UI; every pull request gets a playable preview, a structure check and an honest AI read of the
new passages, and every merge publishes the story.

**Play the story:** https://michaelansel.github.io/NaNoWriMo2026/play.html ·
**Everything else** (proofread copy, story map, all paths, metrics, Story Bible, passage index):
https://michaelansel.github.io/NaNoWriMo2026/

## Before Nov 1

- [ ] `src/StoryTitle.twee`: the story's title (it also titles the landing page)
- [ ] `src/StoryData.twee` `storyStyle`: `perspective`, `protagonist` and `tense`
      (the Style Editor stays off, and says so, until they are set)
- [ ] `src/Start.twee`: the opening passage, linking to the first day's passage
- [ ] Writers added as collaborators, so their `/check-continuity` comments count
- [ ] `/nov1-checklist` prints `READY`

## Writing

Writers never need anything installed. Read **[WRITING-WORKFLOW.md](WRITING-WORKFLOW.md)** for the
daily routine and **[CONTRIBUTING.md](CONTRIBUTING.md)** for a first pull request. In short: add
`src/<INITIALS>-<YYYYMMDD>.twee` whose first passage is `:: Day <N> <INITIALS>`, link to it from an
earlier passage, open a pull request, and read the Build, Continuity and Style comments.

```twee
:: Day 3 EV
Wren took the long way down to the ferry.

[[Wait for Tam->The crossing]]
[[Go alone]]
```

Corrections to the Story Bible (merge two names, drop a false entry, pin a fact, mark a deliberate
mystery) go in [`story-overrides.txt`](story-overrides.txt).

## What runs automatically

| When | What | Where to look |
|---|---|---|
| Every push to a pull request | Build, preview, structure check; Continuity and Style editors on the changed passages | Comments on the pull request, and its checks |
| A collaborator comments `/check-continuity [all] [passage=<name>]` | The editors again | The same comments, updated in place |
| A collaborator comments `/extract-story-bible` | A dry run of what the Story Bible would learn | A Story Bible comment; nothing is saved |
| Merge to `main` | Story Bible extraction, then the site is published | The site, a few minutes later |

AI work runs on a self-hosted runner and is capped at $10 of estimated spend per month; when the
cap is reached the comments say so and name the day it resets.

## Developing the tooling

See **[CLAUDE.md](CLAUDE.md)** for commands and conventions, **[ARCHITECTURE.md](ARCHITECTURE.md)**
for how it fits together, and `features/` for what each part must do.

```bash
pip install -e ".[dev]"          # the nanoif package, pytest, ruff
pytest                           # tests
nanoif check structure src/      # broken links, duplicates, orphans, naming
```

Building the site locally needs [tweego 2.1.1](https://www.motoslave.net/tweego/) with its story
formats plus Harlowe 3.3.9; `.github/actions/build-story/action.yml` shows the exact steps CI runs.
Why the project exists and what comes first: [VISION.md](VISION.md), [PRINCIPLES.md](PRINCIPLES.md),
[PRIORITIES.md](PRIORITIES.md).
