# Case Study: A Gated Documentation Pipeline in an Enterprise Software Team

This is the architecture-level story of the production pipeline that this framework was
abstracted from. It deliberately omits company, product, tracker, and repository names, and
contains no code or prompts from that system. The reusable parts are in the other docs here;
the working open implementation is in `reference-implementation/`.

## Context
A technical writer documenting features for a large enterprise platform had to reconcile five
sources by hand for every story: the work-tracker ticket, a recorded demo, the code, a live
test instance, and the existing published docs. The sources regularly disagreed, and the
disagreement was usually found late, during review.

## What was built
A multi-phase pipeline run from a coding assistant, with a hard human gate between phases:

| Phase | Purpose | Gate that stops it |
|---|---|---|
| Gather: tracker | Pull the work item, its acceptance criteria, and linked code changes | Writer rates the tracker data complete / incomplete / inaccurate / pause |
| Gather: demo | Take a walkthrough transcript, if one exists | Writer chooses what exists: transcript, screenshots, both, or none |
| Gather: code | Read the feature code and its UI tests in local repos | Writer selects which repos hold the feature |
| Gather: live instance | Walk the acceptance criteria on a test instance and record what it actually shows | Writer selects the instance per run |
| Reconcile | Resolve source conflicts using a declared precedence order | Writer confirms scope: new topic, update, or both |
| Scan published docs | Decide whether each change is a new topic or an update | Writer confirms each decision |
| Generate | Build a review document with every claim tagged by source | None, runs on confirmed scope |
| Quality check | Style, structure, and terminology comments in the margin | Writer accepts or rejects each comment |
| SME review | Reviewers comment; writer tags every thread | Pipeline stops if any thread is untagged |
| Authoring | Write the final structured source files | Explicit writer confirmation before anything is written |

## How the gates map to the taxonomy
- Tracker rating and demo selection: **source-trust** and **selection** gates
- Instance and repo choice per run: **selection** gate (never hardcoded)
- Scope confirmation and new-vs-update: **decision** gate
- Quality-check comments: **review-acceptance** gate
- Every review thread must be tagged *make the change / already changed / ignored with reason*: **no-silent-skip** gate
- Final write to the docs source: **explicit-write-confirmation** gate

## Design decisions worth reusing
1. **Rank sources once, apply mechanically.** What is live and observable outranks the demo,
   which outranks code, which outranks the ticket. The writer never re-argues the order per document.
2. **Treat a bad ticket as a normal case.** The tracker gate lets the writer mark it inaccurate,
   and the demo then becomes authoritative. The pipeline does not assume the ticket is right.
3. **Walk the acceptance criteria on the live system.** A deployment check only says the feature
   exists. Walking each criterion records exact labels and values, and exposes criteria that
   have no evidence at all.
4. **Review in the tool reviewers already use.** Comments in a word-processor document meant
   subject-matter experts changed no habits.
5. **No silent skips.** A review comment cannot disappear; it is actioned, verified, or
   ignored with a written reason.
6. **Nothing is hardcoded to one product.** Repos, docs location, release name, and instance are
   configuration or per-run choices, which is what made this framework possible to extract.

## Outcomes
The pipeline accelerates first drafts by gathering and reconciling evidence automatically, while
every consequential decision stays with a human. No quantitative figures are published here.

## Limits and lessons
- The approach depends on having a running environment; without one, the live-system evidence is lost.
- Gates add pauses. They are worth it where a wrong draft is costly, and would be too heavy for trivial edits.
- Extraction of acceptance criteria from free-text tickets is fragile and needs a per-team field mapping.
