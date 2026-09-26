# Vision

## Why we exist

Interactive fiction should be open to writers, not just programmers. We exist to show that a small
group of writers can build a branching story together in a month, using only a web browser, with
automation that catches what people cannot and never gets in their way.

## The goal

On Nov 1 a writer opens a pull request from a browser and within minutes gets an honest AI read of
their new passages, and nothing in the pipeline can fail without saying so.

## The problem

- Interactive fiction tools assume programming, a local setup, and a build pipeline.
- Branching multiplies the places a story can contradict itself, and nobody can re-read every route
  before merging a day's passage.
- Git is intimidating, and one writer's change can break another writer's route.
- Automation that is noisy, or that fails quietly, is worse than none: writers learn to ignore it,
  and the one real problem ships anyway.

## Who we serve

**Primary:** writers taking part in NaNoWriMo who want to write branching fiction without becoming
developers. They work in the GitHub web UI and never install or run anything.

**Secondary:** small writing groups who want daily practice, immediate publication, and quality
from automation rather than gatekeeping.

## What success looks like

**The writers' goal** is a 50,000-word branching story, written together in November. It belongs
to the writers. The tooling cannot write it, only stay out of its way, so word count does not
measure the tooling.

**The tooling succeeds, each November, when:**
- Writers contribute every day from a browser, and no day's passage waits on the tooling.
- Every merged path has been read by the checker and every flagged issue dispositioned by a writer.
- No automated check can fail silently. A check that could not run says so on the pull request.
- A merged passage is playable on the web within minutes.

**Long term:** "How do you keep a branching story consistent?" has an automated, honest answer, and
non-programmers publish complex interactive fiction with confidence.

## Our approach

1. **Zero-barrier contribution**: edit in a browser, install nothing.
2. **Honest automated review**: deterministic structure checks on every pull request, then AI
   editors that read the new passages, quote what they found, and say plainly when they could not
   check.
3. **Many views, one source**: every reading, proofing and review view is generated from the same
   Twee source ([output formats](features/output-formats.md)).
4. **Transparent automation**: writers see what was checked, what was not, and why.

We are not building a writing tool. We remove the obstacles between a writer's idea and a published
interactive story.

## North star

When deciding, ask:
- Does this make it easier for a writer to contribute the next passage?
- Does this make the story's consistency more trustworthy, honestly?
- Does this shorten the time from "I have an idea" to "readers can play it"?
- Could this fail without a writer seeing it? If so, it is not done.
