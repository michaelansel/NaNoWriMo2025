# Principles

How we decide. These are non-negotiable; changing one is an explicit edit to this file, approved by
the user.

## 1. Writers First, Always

**Principle:** Every decision optimizes for the writer's experience, not the developer's convenience.

**This means:**
- Simple beats powerful when they conflict.
- Web-based contribution beats feature-rich local tooling.
- Clear, actionable messages beat technical diagnostics.
- Writer documentation is written for writers, not engineers.

**Trade-offs we accept:** some advanced interactive fiction features are harder to build; technical
users may find the workflow limiting.

**Examples:**
- Yes: edit `.twee` files directly in the GitHub web UI. No: require a local Tweego install.
- Yes: a generated passage index page. No: writers tracking passage names by hand.

---

## 2. Automation Over Gatekeeping

**Principle:** Quality comes from tooling, not from manual review gates or restrictive permissions.
Automation advises; writers edit; a bot never modifies prose on a writer's branch.

**This means:**
- Automate what can be automated; give feedback, not barriers.
- Checks report. They never rewrite a writer's files or commit to a writer's branch.
- An AI finding is advice. A writer decides whether to fix it or dismiss it.
- Trust contributors; verify with tooling.

**Trade-offs we accept:** build infrastructure to maintain; occasional false positives, which
writers dismiss.

**Examples:**
- Yes: AI review on every pull request. No: senior-author approval before merge.
- Yes: the linter reports a formatting problem with its file and line. No: a bot commits the fix.

---

## 3. Fast Feedback Loops

**Principle:** Time from idea to feedback is measured in minutes, not hours or days.

**This means:**
- Every push builds, previews and runs the structure check.
- AI review starts on its own after the build.
- By default, review reads only what changed; the whole story is reviewed on request.
- Status is visible while work is running.

**Trade-offs we accept:** compute and token cost, bounded by the monthly spend cap
([PRIORITIES.md](PRIORITIES.md)); fast pipelines need ongoing attention.

**Examples:**
- Yes: GitHub Actions on every push. No: nightly batch builds.
- Yes: review the changed passages with the routes that lead to them. No: re-review the whole story
  on every push.

---

## 4. Multiple Perspectives, Same Source

**Principle:** Different tasks need different views of the same content. Generate every view from
one source of truth.

**This means:**
- One `src/` of Twee, many generated outputs, each built for one use.
- Never maintain a parallel copy by hand.
- Add a view only when it serves a clear need.

**Trade-offs we accept:** a more complex build; format-specific bugs.

**Examples:**
- Yes: play, proofread, graph, all-paths and passage pages built from `src/`. No: one output trying
  to serve every purpose.
- Yes: the AI reads generated story context. No: pasting passages into prompts by hand.

---

## 5. Transparency and Inspectability

**Principle:** Writers can always see what happened and why. A failure is always visible; a check
that could not run says so.

**This means:**
- "No issues" is only ever a verified result.
- Every AI finding quotes the text that disagrees and names the passages.
- Every AI result says what was read, by which model, and at what cost.
- One comment per check type per pull request, edited in place.

**Trade-offs we accept:** more red checks, because an outage shows as a failure rather than as
quiet; more verbose output.

**Examples:**
- Yes: "could not review: runner offline" with a failed check. No: an empty comment or a green check
  when the AI did not run.
- Yes: a finding with two quotes and two passage names. No: a generic "continuity issue".

---

## 6. Incremental Progress Over Perfection

**Principle:** Ship improvements iteratively. Working now beats perfect later.

**This means:**
- Start with basic functionality; improve from real usage, not hypothetical pain.
- Optimize common paths; tolerate rough edges in rare cases.
- Learn from what shipped, not from what was planned.

**Trade-offs we accept:** some inconsistency while systems evolve; occasional breaking changes when
we learn a better approach.

**Examples:**
- Yes: tune prompts through November against the eval story. No: hold the AI back until it is
  perfect.
- Yes: ship the Continuity Editor with earlier passages only if the Story Bible is not ready. No:
  hold the Continuity Editor for the Story Bible.

---

## 7. Smart Defaults, Escape Hatches

**Principle:** The default path works for most cases. Escape hatches cover the rest.

**This means:**
- Zero configuration produces good results.
- Advanced options exist but are never required.

**Trade-offs we accept:** some duplication between the simple and advanced paths; advanced options
may be less polished.

**Examples:**
- Yes: review of changed passages runs automatically. No: writers choose a mode on every pull request.
- Yes: `/check-continuity all` for a whole-story read on request. No: a separate command per mode.
- Yes: correct the Story Bible by editing one text file in the web UI. No: correcting it requires a
  developer.

---

## 8. Spend Tokens, Not Writer Minutes

**Principle:** Model tokens are cheap; a writer's attention in November is not. Spend tokens to save
writer minutes, within the monthly spend cap.

**This means:**
- AI review runs automatically; writers do not have to ask for it or wait on it.
- Managed inference beats a machine someone has to keep alive.
- Cost is cut by better prompts and sending only what is needed, never by quietly skipping review.
- The cap is hard. When it is reached, review says it did not run (see the Constraints in
  [PRIORITIES.md](PRIORITIES.md)).

**Trade-offs we accept:** a monthly bill up to the cap; late in an expensive month, a pull request may
get no AI read.

**Examples:**
- Yes: read each changed passage with its routes and a compact slice of canon. No: resend the whole
  Story Bible with every route.
- Yes: stop at the cap and say so. No: raise the cap automatically.

---

## 9. Less, Kept True

**Principle:** Keep fewer documents, features and moving parts, and keep every one of them accurate.
What is not kept true is fixed or deleted.

**This means:**
- One home per fact; documents describe the current state.
- A feature writers do not use is removed, not maintained.
- Every part that must be alive in November has a failure a writer can see.
- A test that cannot fail is deleted or fixed.

**Trade-offs we accept:** things get deleted that someone might want later; git history is the
archive.

**Examples:**
- Yes: delete a feature nobody used last season. No: keep it "just in case".
- Yes: one link parser. No: six that disagree.

---

## Applying these principles

The principles rank in the order above: Writers First, Automation, Fast Feedback, Multiple
Perspectives, Transparency, Incremental, Smart Defaults, Spend Tokens, Less Kept True.

**When they conflict:** Writers First wins. An honest "could not check" beats a fast or flattering
answer. The spend cap beats Spend Tokens. Fast Feedback beats perfection. Transparency beats
simplicity.

## Strategic decision: pull requests are the writer's interface

- Writers commit through the GitHub web UI, see results in pull request comments and the preview,
  and run the few on-demand commands as pull request comments ([WRITING-WORKFLOW.md](WRITING-WORKFLOW.md)).
- Writers never install tools, run commands, or run Claude in the repository.
- The `nanoif` CLI is a developer tool. It is not documented in writer guides and is not a supported
  way to contribute.
- Feature notes describe pull-request workflows; error messages point writers to pull request
  comments, never to the CLI.

## What we do not optimize for

- Technical elegance over the writer's experience
- Feature completeness over time to value
- Flexibility over focused functionality
- Supporting every possible workflow
- Beautiful code over working software
- Comprehensive design documents over shipping

These are not bad; they are not what this project optimizes for.
