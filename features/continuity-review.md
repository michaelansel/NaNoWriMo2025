# Continuity review

**Status**: building

## User problem
Branching multiplies the places a story can contradict itself, and no writer can re-read every
route before merging a day's passage. An AI reader could, but only if writers trust it. A reader
that is usually wrong, repeats the same complaint once per route, floods the pull request with
comments, or goes quiet when it breaks teaches writers to ignore it, and then the one real
contradiction ships anyway. Silence must mean "read and clean", never "could not read".

## User stories
- As a writer, I want the passages I changed read against everything that leads to them, so that
  I hear about a contradiction before a reader does.
- As a writer, I want each problem reported once with the two quotes that disagree, so that I can
  judge it in a minute without opening other files.
- As a writer, I want my point of view, tense and protagonist checked against the story's
  settings, so that a slip in one paragraph is caught.
- As a writer, I want to dismiss a finding I disagree with, so that it stops coming back.
- As a writer, I want to be told plainly when the AI could not read my passages, so that no
  comment never means "all clear" by accident.

## Behavior
**Trigger.** Every push to a pull request from a branch of this repository that adds or changes
passages. The review runs after the build, on the exe.dev runner; if that runner is offline, it
says so (see Edge cases). All AI work shares a monthly spend cap (see `PRIORITIES.md`,
Constraints); once it is reached, reviews say they did not run until the 1st.

**Two editors**, each reviewing every new or changed passage:
- **Continuity Editor** reads the passage with the passages that lead to it on its routes and the
  Story Bible facts for the people, places and things it mentions ([story-bible](story-bible.md)).
  It reports contradictions between the passage and one earlier passage or one established fact.
  Until the Story Bible is extracted, it has earlier passages only, and its header says which
  canon it used.
- **Style Editor** checks the passage's point of view, tense and protagonist against `storyStyle`
  in `StoryData`.

**What the writer sees.** One comment per editor on the pull request, edited in place on every
push, and one check run per editor (`Continuity Editor`, `Style Editor`). While a review runs,
each comment says "running" instead of showing the previous result.

- The header: passages reviewed, findings, suppressed findings, model, the tokens and estimated
  cost of the whole review run, a link to that run, and (Continuity only) the Story Bible canon
  it checked against.
- Each finding: its id (`f-` and 8 hex digits), severity, confidence, one sentence, the quotes that
  disagree with the passage name for each, and the exact `/dismiss` command for it. Severity:
  *critical* = impossible on this route; *major* = a reader will notice; *minor* = a careful
  reader might notice.
- Collapsed at the end: findings suppressed by a dismissal or an intentional conflict, and
  "unverified" findings whose quotes could not be found in the passages.
- The check run: success when every passage was reviewed and nothing was found; neutral when
  there are findings; failure when any passage could not be reviewed.

For example, on the eval story a finding reads: *major, "Tam has poled the river for forty years
in `Day 1 EV` but thirty in `Back at the ferry`"*, with one quote from each passage.

**Commands** (comment on the pull request; only the repository's owners, members and
collaborators are obeyed, and nobody else's comment costs anything):
- `/check-continuity` reviews the changed passages again; `/check-continuity all` reviews every
  passage, stating the estimated cost first and the actual cost after;
  `/check-continuity passage=<name>` reviews one passage again. When the editors already reviewed
  this same commit, that passage's new result replaces its old one and every other passage's
  result stays, so the check run still reflects the whole review. When they have not (for
  example the last review was of an earlier push, or did not run), the comments show only that
  passage, say the other passages are not shown, and the check run is never success.
- `/dismiss f-xxxxxxxx [reason]` records the dismissal and moves the finding to the collapsed
  section. No model is called.

## Acceptance criteria
- AC-continuity-review-1: On every push to a pull request from a branch of this repository, each new or changed passage is reviewed once by the Continuity Editor and once by the Style Editor. (verify: workflow)
- AC-continuity-review-2: A pull request has exactly one Continuity Editor comment and one Style Editor comment, each found by its HTML marker and edited in place on every run.
- AC-continuity-review-3: Each finding shows its `f-` id, severity, confidence, a one-sentence description, a quote with its passage name from each passage involved, and the `/dismiss` command for that id.
- AC-continuity-review-4: The same contradiction between the same two passages, seen from several routes, appears as one finding.
- AC-continuity-review-5: A finding whose quotes are not found verbatim in the cited passages is listed only in the collapsed "unverified" section and is not counted as a finding.
- AC-continuity-review-6: Each comment's header shows the passages reviewed, findings, suppressed findings, model, the input and output tokens and estimated cost of the whole review run, and a link to that run.
- AC-continuity-review-7: Each editor's check run is success when every passage was reviewed with no findings, neutral when there are findings, and failure when any passage could not be reviewed; after `/check-continuity passage=<name>`, "every passage" is that passage plus every other passage of the last review of the same commit, and with no such review the check run is never success.
- AC-continuity-review-8: A passage that could not be reviewed (provider error after one retry, or too long for the model) is listed by name with the reason, and its editor's comment never reports "no issues" for it.
- AC-continuity-review-9: When the exe.dev runner is offline, each editor's comment says "AI review unavailable" with the reason and its check run fails, while the build and structure check still run.
- AC-continuity-review-10: `/check-continuity`, `/check-continuity all` and `/check-continuity passage=<name>` from an owner, member or collaborator start the matching review; the same comment from anyone else starts no job and spends no tokens.
- AC-continuity-review-11: `/check-continuity all` posts its estimated cost before the run and the actual cost in the finished comment. (verify: planned)
- AC-continuity-review-12: `/dismiss f-xxxxxxxx [reason]` from a collaborator records the dismissal on `main` and re-renders the comment with that finding in the suppressed section, without calling a model.
- AC-continuity-review-13: A dismissed finding stays suppressed on later runs while both of its passages are unchanged, and is reported again when either passage changes.
- AC-continuity-review-14: A finding against an established fact that belongs to a conflict marked in `story-overrides.txt` as intentional (by `c-<id>` or by label) is listed only among suppressed findings with the reason `intentional-conflict:<id or label>`, and is not counted as a finding.
- AC-continuity-review-15: Run over the eval story, the Continuity Editor reports the contradictions `c-tam-years` and `c-pip-age`. (verify: workflow)
- AC-continuity-review-16: Run over the eval story, the Continuity Editor reports at least two of the planted defects `d-marsh-alive`, `d-lantern-rule` and `d-timeline`. (verify: workflow)
- AC-continuity-review-17: Run over the eval story, both editors together report at most one finding across the clean routes `clean-crossing` and `clean-widow`. (verify: workflow)
- AC-continuity-review-18: Run over the eval story, the Style Editor reports `d-pov` and `d-tense`, each as minor. (verify: workflow)
- AC-continuity-review-19: Of pull requests that change up to three passages, 95 in 100 are reviewed within 10 minutes of their build finishing, and each costs under $0.25. (verify: manual)
- AC-continuity-review-20: `/check-continuity all` on a story of up to 100 passages uses at most 1.5M input tokens and costs under $5. (verify: workflow)
- AC-continuity-review-21: A model answer cut off by the length limit is an error for that call, never an empty result.
- AC-continuity-review-22: A model answer that still fails its schema after one repair round is an error for that call; the repair round tells the model what was wrong.
- AC-continuity-review-23: A provider that is unreachable, times out, or answers with an HTTP error produces an error for that call, never a result.
- AC-continuity-review-24: A call that would take the job past its token budget is refused before it is sent.
- AC-continuity-review-25: The cost figures behind the comment header total the tokens and estimated cost of every call in the run, and mark the cost as unknown, not zero, for a model with no known price.
- AC-continuity-review-26: Scoring an empty result against the eval story gives zero on every recall metric, and an eval run missing a metric is a regression, never a pass.
- AC-continuity-review-27: Run over the regression fixtures for two known false-positive patterns, `height-sitting-vs-standing` (a size given sitting and standing) and `sword-hand-after-fall` (a position that changes after an event), the Continuity Editor reports no finding. (verify: planned)
- AC-continuity-review-28: When the review did not run for a commit, each editor's comment says it did not run for that commit, gives the reason, says nothing was checked, and shows no earlier result, and its check run on that commit is failure.
- AC-continuity-review-29: When a push's build fails or the AI runner check fails, that push's run posts the AC-continuity-review-28 comments and check runs, and so does `/check-continuity` when its build or runner check fails. (verify: workflow)
- AC-continuity-review-30: After `/check-continuity passage=<name>`, each editor's comment keeps every other passage's findings and could-not-review entries from the last review of the same commit; with no such review, its title says only that passage was re-checked and it says the other passages are not shown.
- AC-continuity-review-31: When this month's estimated AI spend has reached the cap, no model call is made, and each editor's comment and check run are those of AC-continuity-review-28 with the reason `monthly AI spend cap reached: $X.XX of $C.CC in YYYY-MM (resets YYYY-MM-01 UTC)`, naming the reset date instead of suggesting a retry; the check run is failure, never success or neutral.
- AC-continuity-review-32: A call that would take this month's estimated spend past the cap is refused before it is sent; every passage not yet reviewed is listed as could-not-review with the AC-continuity-review-31 reason, passages already reviewed keep their findings, and the check run is failure.
- AC-continuity-review-33: An unreadable or invalid spend ledger stops AI review before any model call with a visible reason naming the ledger problem, and the comments and check runs are those of AC-continuity-review-28; it is never counted as zero spend.
- AC-continuity-review-34: When the monthly spend cap is reached, the build, the preview and the structure check still run and report as usual. (verify: workflow)
- AC-continuity-review-35: `/check-continuity all` whose estimated cost would take this month's spend past the cap starts no review, calls no model, and replies with the AC-continuity-review-31 reason instead of an estimate. (verify: planned)
- AC-continuity-review-36: The Continuity Editor comment header states the Story Bible canon it used: the extraction date and commit, the number of established facts offered, the number of out-of-date facts left out, and the reviewed passages the Bible has not read; with no saved extraction it says only earlier passages were checked. A missing or unreadable canon stops the review with the reason shown, never a review against no established facts.
- AC-continuity-review-37: Run over the eval story with its `story-overrides.txt`, `c-widow-never-wife` is never reported as a finding. (verify: workflow)

## Edge cases
- **Runner offline or gateway out of tokens**: "AI review unavailable" with the reason, a failed
  check run, and no findings shown as if the review happened (AC-continuity-review-9).
- **Monthly AI spend cap reached**: both comments say the review did not run, give the spend and
  the reset date, and both check runs fail; a review that reaches the cap part-way lists the
  unread passages as could not check. One `/check-continuity all` (AC-continuity-review-20) may
  use up to half the month's cap, so it is refused when less than its estimate remains
  (AC-continuity-review-31 to AC-continuity-review-35).
- **Passage too long for the model**: listed as "could not check (skipped): too long", check run
  failure.
- **Build failed, or the AI runner check failed** (for example a mistyped `AI_RUNNER` setting):
  the review has nothing to read or nowhere to run; both comments say it did not run for that
  commit and why, the old result is removed, and both check runs fail (AC-continuity-review-28,
  AC-continuity-review-29).
- **One passage re-checked after a new push, before that push was reviewed**: there is no review
  of the same commit to add it to, so the comments show only that passage and say so
  (AC-continuity-review-30); `/check-continuity` brings back every changed passage.
- **Pull request from a fork**: the editors do not run and post nothing; the `ai-review` check
  shows as skipped, and `/check-continuity` replies that forks are not reviewed. No paid inference
  runs for a fork.
- **No passages changed** (for example only `story-overrides.txt`): the comments say nothing
  needed review; the check runs succeed.
- **Passage not yet in the Story Bible**: it is still reviewed against earlier passages; the
  header names it as not in the Bible (AC-continuity-review-36).
- **An established fact whose passage changed since extraction**: it is left out of the canon
  and counted in the header as out of date.
- **Two pushes close together**: the newer run replaces the older one; one comment per editor.

## Soft goals
- At least one in three findings is acted on by a writer rather than dismissed or ignored.
- Writers read the editors' comments because they are short and usually right.

## Out of scope
- Rewriting prose, suggesting replacement text, or committing anything.
- Grammar, spelling, pacing, choice design and endings.
- Blocking merges: the check runs advise; the writer decides.
- The Story Bible page and its extraction ([story-bible](story-bible.md)).
