# ADR-027: The writer's guide is rendered from Markdown into `dist/guide.html`

Status: Accepted

## Context

`WRITERS-GUIDE.md` at the repository root is the writer-facing guide. Writers should also be able
to read it as a page on the site and in the pull request `story-preview`, linked from the landing
page. The guide uses headings, paragraphs, bold, inline code, links, ordered and bullet lists,
pipe tables whose cells contain escaped `\|`, a fenced code block and a `- [ ]` task list.
Collaborators edit it in the GitHub web UI, and it may absorb `CONTRIBUTING.md` and
`WRITING-WORKFLOW.md` later, so the Markdown it uses will grow.

The same file is read in two places: on GitHub at the repository root, and on Pages from `dist/`.
A relative link resolves in only one of them. The package's runtime dependencies are `jinja2`,
`openai` and `jsonschema` (ADR-015). The site is built only on hosted runners.

## Decision

- **Renderer: `markdown-it-py` with `mdit-py-plugins`**, added to `[project].dependencies` with
  `~=` pins like the others. Parser: the `commonmark` preset with `html` off, the `table` rule
  enabled, and the `tasklists` plugin and the `anchors` plugin (ids on all heading levels). Raw HTML in the guide shows as escaped
  text. markdown-it's link validation leaves `javascript:`, `vbscript:`, `file:` and `data:`
  targets unlinked. Markdown syntax outside this set shows as literal text on the page.
- **One Markdown renderer.** `nanoif.formats.guide` is the only code that turns Markdown into
  HTML. `markdown_it` is imported there only. The CLI imports that module inside `_build_guide`,
  as it does for every other build step, so other commands never load it. The GitHub reporter
  writes Markdown and `github.sanitize` neutralizes it; those are separate concerns.
- **Placement.** `nanoif/formats/guide.py` has `build_guide(source: Path, out_dir: Path) -> Path`.
  `ProjectPaths.writers_guide` is `<repo>/WRITERS-GUIDE.md`. The page template is
  `nanoif/templates/html/guide.html.jinja2`, loaded through `formats.common.html_environment()`
  and styled like the other pages. The rendered body is the template's only `|safe` value. The
  page title comes from the guide's first level-1 heading.
- **CLI and order.** `nanoif build guide --repo <repo>` writes `dist/guide.html`. `build all` runs
  it after `passages` and before `landing`, so the landing page is still the last step and every
  page it links to exists before it is written. The guide reads no core artifact.
- **Landing.** `landing/index.html` gets a static "For writers" section that links `guide.html`
  (ADR-011: the landing links stay hand-written). The build either writes `guide.html` or fails,
  so this link cannot point at a missing page.
- **Links.** Every link and image target in the guide must be one of two things:
  - an `https://` URL
  - a `#fragment` that matches a heading id on the rendered page

  Any other target fails the build. That includes relative paths such as `story-overrides.txt`,
  `src/` or `CONTRIBUTING.md`, and `http:` or `mailto:` targets. The guide names repository files
  in inline code instead. Heading ids use a slug that matches GitHub's for ASCII headings, so a
  `#fragment` link works in both places.
- **Workflow.** No change. The `build-story` action runs `nanoif build all`, and `dist/` is
  already the `story-preview` artifact and the Pages upload. `build-and-deploy.yml` has no path
  filter, so a push to `main` that changes only the guide redeploys it.
- **Failure.** `build_guide` raises `BuildError` (the CLI prints one `error:` line, exits 1) when:
  - the file is missing or unreadable, or is not UTF-8
  - it is empty or only whitespace, or has no level-1 heading
  - a link target is not allowed, or a `#fragment` matches no heading
  - `markdown-it-py` or `mdit-py-plugins` cannot be imported

  The page is rendered completely before anything is written, so a failed build leaves no empty
  or partial `guide.html`.

## Consequences

### Positive

- CommonMark and GFM-table behaviour, including `\|` in cells, comes from a maintained parser
  instead of code this project must keep correct.
- Collaborator-edited content cannot inject script or markup into the site.
- A broken link or anchor in the guide shows up as a failed build, not a dead link on the site.
- The PR preview and Pages show the same guide with no extra workflow steps.

### Negative

- There are two more runtime dependencies (plus `mdurl`). Every job that runs `pip install -e .`
  installs them, including jobs on the exe runner, which never render the guide.
- `WRITERS-GUIDE.md` is now a build input. Renaming it, deleting it, or adding a relative link to
  it turns every PR build red until it is fixed. This is visible, but not something writers caused.
- The guide cannot link to repository files. Where it needs to point at one, it names the file.

## Alternatives Considered

1. **Own renderer for the subset used**: this means maintaining table-cell escaping, lazy list
   continuation and code-span rules ourselves. Syntax outside the subset would render wrong
   without any error, and the subset will grow if the other writer docs are merged into the guide.
2. **`markdown` (Python-Markdown)**: not CommonMark. Its tables and task lists need extensions or
   third-party packages, and it passes raw HTML through by default.
3. **`mistune`**: fast and has plugins, but its escaping and table behaviour have changed between
   major versions, and it has no anchors plugin to match GitHub heading ids.
4. **Rewrite relative links to GitHub URLs using `GITHUB_REPOSITORY`**: local and CI builds would
   produce different pages, and the page would carry the repository name.
5. **Leave relative links alone**: every one of them would be a dead link either on GitHub or on
   the site.
6. **Generate the landing section from the build**: ADR-011 keeps the landing links static, and a
   generated section adds a second way for a link to go missing.

## References

- ADR-011 (landing page), ADR-015 (package, typed errors), ADR-018 (visible failures)
- `features/output-formats.md` (AC-output-formats-2: every landing link opens an existing page)
