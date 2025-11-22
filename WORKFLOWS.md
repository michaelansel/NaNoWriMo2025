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

## Automation

When you commit, GitHub Actions automatically:
- Updates `Resource-Passage Names` file
- Builds 4 formats: Harlowe (playable), Paperthin (proofread), DotGraph (graph), AllPaths (continuity)
- Creates preview artifact
- Posts build stats comment

---

## Checklist

- [ ] Edit existing `.twee` file → add link to today's passage
- [ ] Create `src/{INITIALS}-YYMMDD.twee` with new content
- [ ] Test preview artifact
- [ ] Merge

**Remember:** Two files change every day (one edit + one create)
