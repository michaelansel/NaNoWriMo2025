# Daily Writing Workflow

## The Pattern

Every day requires **two changes** to connect new content to the story:

1. **Edit existing passage** - Add a branching choice
2. **Create new file** - Write today's content

Both changes go in the same PR.

---

## Example: Day 21

### 1. Edit `src/mansel-20251112.twee`
```twee
[[Collect snacks]]
[[Empty kitchen->Day 21 KEB]]

::Collect snacks
...
```

### 2. Create `src/KEB-251121.twee`
```twee
:: Day 21 KEB

Javlyn checked the cabinet and found it bare of any meat...
```

---

## File Naming

Pattern: `{INITIALS}-YYMMDD.twee`
- `KEB-251121.twee` (November 21, 2025)
- `mansel-20251112.twee` (November 12, 2025)

**Must end with `.twee` extension.**

---

## Twee Syntax

```twee
:: Passage Name

Content here.

[[Display text->Destination]]
[[Simple Link]]
```

**Key rules:**
- Passage names must be unique across all files
- Links reference passage names (not filenames)
- `[[Empty kitchen->Day 21 KEB]]` looks for `:: Day 21 KEB` anywhere

---

## Workflow (GitHub Web UI)

1. Edit existing file → add branching choice → commit to new branch → create PR
2. On same branch: Add new file with today's content → commit
3. Automation runs: `Auto-update Resource-Passage Names` commit + builds
4. Download `story-preview` artifact from Actions → test `index.html`
5. Merge when ready → live in ~2 minutes

---

## What Happens Automatically

When you push changes, the system handles everything for you. Here's what runs and when:

### Automatic: Generates Outputs You Can Browse

These run on every build and produce pages you can view on GitHub Pages:

| Output | What It Is | Where to Find It |
|--------|-----------|------------------|
| **Story (Harlowe)** | Playable interactive story | `index.html` |
| **Proofread (Paperthin)** | Linear text for reading | `proofread.html` |
| **Structure (DotGraph)** | Visual story map | `graph.html` |
| **AllPaths** | All possible playthroughs with dates | `allpaths.html` |
| **Story Bible** | World facts and characters | `story-bible.html` |
| **Writing Metrics** | Word counts and statistics | `metrics.html` |

### Automatic: Maintains Files For You

These run on every build and update repository files:

| What | Effect |
|------|--------|
| **Formatting Linter** | Auto-fixes .twee formatting issues (commits changes) |
| **Resource Tracking** | Updates passage catalog in `Resource-Passage Names` |

### Automatic: Gives You Feedback

These run on PRs and post results as comments:

| What | When | Where You See It |
|------|------|------------------|
| **AI Copy Editing Team** | Every PR | PR comment with validation results |
| **Build Status** | Every push | Green/red checkmark on PR |

### Manual: Webhook Commands (PR Comments)

Comment these on a PR when you need them:

| Command | What It Does |
|---------|--------------|
| `/extract-story-bible` | Re-extracts Story Bible from current content |
| `/check-continuity` | Run validation (default: new paths only) |
| `/check-continuity modified` | Validate new + modified paths |
| `/check-continuity all` | Full validation of all paths |

**Most of the time, you don't need manual commands.** Everything runs automatically.

---

## Checklist

- [ ] Edit existing `.twee` file → add link to today's passage
- [ ] Create `src/{INITIALS}-YYMMDD.twee` with new content
- [ ] Test preview artifact
- [ ] Merge

**Remember:** Two files change every day (one edit + one create)
