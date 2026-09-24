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
says so (see Edge cases).

**Two editors**, each reviewing every new or changed passage:
- **Continuity Editor** reads the passage with the passages that lead to it on its routes and the
  Story Bible facts for the people, places and things it mentions ([story-bible](story-bible.md)).
  It reports contradictions between the passage and one earlier passage or one established fact.
- **Style Editor** checks the passage's point of view, tense and protagonist against `storyStyle`
  in `StoryData`.

**What the writer sees.** One comment per editor on the pull request, edited in place on every
push, and one check run per editor (`Continuity`, `Style`).

- The header: passages reviewed, findings, suppressed findings, model, tokens, estimated cost,
  and the commit reviewed.
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
  `/check-continuity passage=<name>` reviews one passage.
- `/dismiss f-xxxxxxxx [reason]` records the dismissal and moves the finding to the collapsed
  section. No model is called.

## Acceptance criteria
- AC-continuity-review-1: On every push to a pull request from a branch of this repository, each new or changed passage is reviewed once by the Continuity Editor and once by the Style Editor. (verify: planned)
- AC-continuity-review-2: A pull request has exactly one Continuity Editor comment and one Style Editor comment, each found by its HTML marker and edited in place on every run. (verify: planned)
- AC-continuity-review-3: Each finding shows its `f-` id, severity, confidence, a one-sentence description, a quote with its passage name from each passage involved, and the `/dismiss` command for that id. (verify: planned)
- AC-continuity-review-4: The same contradiction between the same two passages, seen from several routes, appears as one finding. (verify: planned)
- AC-continuity-review-5: A finding whose quotes are not found verbatim in the cited passages is listed only in the collapsed "unverified" section and is not counted as a finding. (verify: planned)
- AC-continuity-review-6: Each comment's header shows the passages reviewed, findings, suppressed findings, model, input and output tokens, estimated cost, and the commit reviewed. (verify: planned)
- AC-continuity-review-7: Each editor's check run is success when every passage was reviewed with no findings, neutral when there are findings, and failure when any passage could not be reviewed. (verify: planned)
- AC-continuity-review-8: A passage that could not be reviewed (provider error after one retry, or too long for the model) is listed by name with the reason, and its editor's comment never reports "no issues" for it. (verify: planned)
- AC-continuity-review-9: When the exe.dev runner is offline, each editor's comment says "AI review unavailable" with the reason and its check run fails, while the build and structure check still run. (verify: planned)
- AC-continuity-review-10: `/check-continuity`, `/check-continuity all` and `/check-continuity passage=<name>` from an owner, member or collaborator start the matching review; the same comment from anyone else starts no job and spends no tokens. (verify: planned)
- AC-continuity-review-11: `/check-continuity all` posts its estimated cost before the run and the actual cost in the finished comment. (verify: planned)
- AC-continuity-review-12: `/dismiss f-xxxxxxxx [reason]` from a collaborator records the dismissal on `main` and re-renders the comment with that finding in the suppressed section, without calling a model. (verify: planned)
- AC-continuity-review-13: A dismissed finding stays suppressed on later runs while both of its passages are unchanged, and is reported again when either passage changes. (verify: planned)
- AC-continuity-review-14: A contradiction listed as `intentional-conflict:` in `story-overrides.txt` is never reported as a finding; on the eval story, `c-widow-never-wife` is never reported. (verify: planned)
- AC-continuity-review-15: Run over the eval story, the Continuity Editor reports the contradictions `c-tam-years` and `c-pip-age`. (verify: planned)
- AC-continuity-review-16: Run over the eval story, the Continuity Editor reports at least two of the planted defects `d-marsh-alive`, `d-lantern-rule` and `d-timeline`. (verify: planned)
- AC-continuity-review-17: Run over the eval story, both editors together report at most one finding across the clean routes `clean-crossing` and `clean-widow`. (verify: planned)
- AC-continuity-review-18: Run over the eval story, the Style Editor reports `d-pov` and `d-tense`, each as minor. (verify: planned)
- AC-continuity-review-19: Of pull requests that change up to three passages, 95 in 100 are reviewed within 10 minutes of their build finishing, and each costs under $0.25. (verify: planned)
- AC-continuity-review-20: `/check-continuity all` on a story of up to 100 passages uses at most 1.5M input tokens and costs under $5. (verify: planned)
- AC-continuity-review-21: A model answer cut off by the length limit is an error for that call, never an empty result.
- AC-continuity-review-22: A model answer that still fails its schema after one repair round is an error for that call; the repair round tells the model what was wrong.
- AC-continuity-review-23: A provider that is unreachable, times out, or answers with an HTTP error produces an error for that call, never a result.
- AC-continuity-review-24: A call that would take the job past its token budget is refused before it is sent.
- AC-continuity-review-25: The cost figures behind the comment header total the tokens and estimated cost of every call in the run, and mark the cost as unknown, not zero, for a model with no known price.
- AC-continuity-review-26: Scoring an empty result against the eval story gives zero on every recall metric, and an eval run missing a metric is a regression, never a pass.
- AC-continuity-review-27: The regression fixtures for two known false-positive patterns (a narrator correcting a count mid-sentence; one person described in different words on two routes) produce no finding. (verify: planned)

## Edge cases
- **Runner offline or gateway out of tokens**: "AI review unavailable" with the reason, a failed
  check run, and no findings shown as if the review happened (AC-continuity-review-9).
- **Passage too long for the model**: listed as "not reviewed: too long", check run failure.
- **Pull request from a fork**: the editors do not run; the check run summary says the review is
  skipped for forks. No paid inference runs for a fork.
- **No passages changed** (for example only `story-overrides.txt`): the comments say nothing
  needed review; the check runs succeed.
- **Passage not yet in the Story Bible**: it is still reviewed against earlier passages; the
  header notes that no established facts were available for it.
- **Two pushes close together**: the newer run replaces the older one; one comment per editor.

## Soft goals
- At least one in three findings is acted on by a writer rather than dismissed or ignored.
- Writers read the editors' comments because they are short and usually right.

## Out of scope
- Rewriting prose, suggesting replacement text, or committing anything.
- Grammar, spelling, pacing, choice design and endings.
- Blocking merges: the check runs advise; the writer decides.
- The Story Bible page and its extraction ([story-bible](story-bible.md)).
