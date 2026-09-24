# ADR-017: Git-based categorization, no validation cache; `allpaths-index.json` and `changes.json`

## Status

Status: Accepted
Supersedes: ADR-001, ADR-002, ADR-004, ADR-007, ADR-008

## Context

AllPaths categorized paths as new, modified or unchanged by comparing fingerprints with a committed `allpaths-validation-status.json` that the webhook rewrote on writers' branches. The cache caused merge conflicts and bot commits, its "validated" flag was never used by writers, and the fingerprints and git history disagreed. The AI editors no longer read path text files: they need to know which passages changed against the PR's base (ADR-019).

## Decision

Categorization is computed from git at build time. There is no validation cache, no "validated" state and no `/approve-path`.

- **Base.** On a PR the workflow exports `GITHUB_MERGE_BASE` (`git merge-base HEAD origin/<base>`); if `GITHUB_BASE_REF` is set without it, the build fails. Locally the base is `HEAD`.
- **Comparison.** The base's `src/` is read from git blobs in one `git cat-file --batch` and parsed with the same parser as the working tree (`nanoif.graph.categorize`). A passage is `changed` when its text differs and `new` when the base lacks its name; `prose_changed` ignores link markup and whitespace.
- **Path category**: a route that existed in the base is `modified` if any passage on it changed, else `unchanged`; a new route is `new` when it carries new or changed prose, else `modified`.
- **Identifiers.** Path id: first 8 hex of MD5 over `name:text` lines of the route, so it changes when any passage on it changes. Passage id: first 12 hex of MD5 of the name (hides names like `Day <N> <INITIALS>` from reviewers). Passage `content_hash`: first 16 hex of SHA-256 of the text; dismissals and the Story Bible key on it.
- **Enumeration** is one depth-first walk in link order. Broken links and cycles are reported and not followed, never turned into fake endings. Each path record is computed once and feeds every output; there are no intermediate `paths*.json` files.
- **Dates** come from one `git log` over `src/`, never git calls per path.
- **Contracts** (written by `nanoif build allpaths`, schemas in `nanoif/schemas/artifacts/`, validated at write time, uploaded in the `story-preview` artifact):
  - `dist/changes.json`: `{base_ref, base_sha, changed[], new[], removed[]}`, sorted passage names. Read by review units for `--mode changed`.
  - `dist/allpaths-index.json`: `{base_ref, base_sha, story_title, paths[{id, route, passage_ids, category, files, created, modified}], passages[{name, id, file, changed_vs_base, new_vs_base}], broken_links, cycles}`. Read by pages and tools that need routes without re-enumerating.
- AllPaths text files and `allpaths.html` remain reading formats for writers; one page is generated for PR previews and deploys alike.

## Consequences

### Positive

- No committed state for categorization, so no merge conflicts and no bot commits.
- New/modified is exactly what the PR diff says, against the same base the reviewer sees.
- The AI editors depend on two small validated files, not on text-file layout.

### Negative

- A shallow clone cannot categorize; the build job must fetch full history.
- Content-sensitive path ids change whenever a passage on the route changes, so path ids are not stable references across edits; passage names and finding keys are.

## Alternatives Considered

1. **Keep the cache, stop committing it to PR branches**: still conflicts on main and still duplicates git.
2. **Actions cache or a data branch for categorization**: state that can drift from the diff it describes.
3. **Route-only path ids**: stable across edits, but then two builds with different prose share one id and file name.

## References

- ADR-015 (package and artifacts), ADR-019 (review units), `nanoif/formats/allpaths/generator.py`, `nanoif/graph/categorize.py`
