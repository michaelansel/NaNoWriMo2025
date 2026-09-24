---
paths:
  - "src/**/*.twee"
---

# Twee files

- Prose files are `src/<INITIALS>-<YYYYMMDD>.twee` and belong to writers. Do not open them for editing unless the user named the file. Infra passages (`Start`, `StoryData`, `StoryTitle`, `StoryStyles`, `PathIdDisplay`) are yours.
- `src/PathIdLookup.twee` is generated at build time and gitignored; never write it by hand.
- Entry passage of a prose file is `:: Day <N> <INITIALS>`; other passage names are natural language. `nanoif check structure` reports naming drift.
- Links: `[[Text->Target]]`, `[[Target]]`, or `(link-goto:)`; the target is the rightmost `->`. Every target must exist; broken links fail the Structure check.
- Formatting rules `nanoif lint` reports (never auto-fixes): space after `::` in headers; one blank line after a header (except `StoryData`, `StoryTitle`, `StoryStylesheet`, `StoryBanner`, `StoryMenu`, `StoryInit`, and `[stylesheet]`/`[script]` passages); exactly one blank line before a header; no trailing whitespace; file ends with exactly one newline; no consecutive blank lines; blank line before and after a link block, none between links.
- Smart quotes are prose. There is no rule about them.
- `StoryData` holds the IFID (uppercase UUIDv4, never reuse a previous year's), `format-version` pinned to what the bundled tweego ships, and `storyStyle` (`perspective`, `protagonist`, `tense`) that the Style Editor reads.
- Tags in use: `[stylesheet]`, `[footer]`. Do not invent new ones without an entry in `ARCHITECTURE.md`.
