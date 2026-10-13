---
name: doc-pipeline
description: >
  Tracker-agnostic documentation pipeline with human gates. Takes a work item from the team's
  tracker (GitHub, Jira, or a pasted spec), gathers evidence from code, tests, a running app and
  existing docs, reconciles disagreements by a declared source ranking, and produces a Word review
  document with source-tagged claims, a style-guide quality pass, SME/PM checklists and screenshots.
  Trigger: "/doc-pipeline", "document <key>", "run the doc pipeline for <key>".
---

# Goal
Draft documentation for one feature that is checked against what was actually built, and keep the
writer in control at every decision. Nothing here is specific to a company, tracker or doc format;
everything comes from config and flags.

## Who does what
| Part | Does |
|---|---|
| **You (Claude)** | Read the ticket, code, tests and running app; write the findings file and the draft text; ask the writer at each gate |
| **`python3 -m docaidev`** | Fetch, reconcile by precedence, detect conflicts, scan docs, seed/capture/clean up, run the style check, build the document, enforce gates |
| **The writer** | Rate the tracker data, tag review comments, type the write confirmation |

Never answer a gate for the writer. Never pass `--confirm` unless the writer typed the phrase.

## Step 0: pre-flight (stop on any failure)
0. First time on this machine: `sh install.sh` (checks Python 3.9+, installs Playwright and Chromium, runs the tests).
1. `python3 -m docaidev test`. No config? Tell the writer to run
   `python3 -m docaidev setup --tracker <github|jira|paste> [--repo OWNER/REPO | --base-url URL --ac-field customfield_N]`.
2. Confirm each repo path to review exists; ask which repos hold the feature code.
3. If an environment check is wanted: the app is running, the URL is localhost (seeding writes data;
   a non-local URL needs `--allow-remote-seed` and an explicit yes from the writer), and Playwright is installed.
4. Ask for anything missing: product name, release, author, SME, epic, sprint (these go in `meta.json`).

## Step 1: fetch and the accuracy gate
Run `python3 -m docaidev fetch <key>`. Show the coverage list (found / MISSING per field, essential
ones flagged). Ask the writer: **1 complete, 2 incomplete, 3 inaccurate, 4 pause**. Use the answer as
`--accuracy`. Option 3 excludes the tracker as a source; option 4 stops.

## Step 2: gather evidence into files
Write these next to the output, as JSON/Markdown the CLI reads:
- `observations.json`: `[{"topic": "Save button label", "value": "Send invoice", "source": "repo"}]`.
  One entry per fact you verified in code, tests or a walkthrough. Use sources the style of
  `live`, `walkthrough`, `repo`. Never record a fact you did not see; leave it out instead.
- `seed.json` (only if an environment check is wanted): records to seed, what to read off the
  page (`observe`), and screenshots (`shots`). Facts read from the page become `live` findings.
- Ticket facts: acceptance-criteria lines written `Topic: value` are read as `tracker` facts.

## Step 3: write the draft text
Write `draft.md` in this shape; the tool never invents prose. Use `{Topic name}` placeholders
for every UI label or value, so a wrong ticket label can never reach the text.
```
## Release notes            (### Highlights / ### New in this release / ### UI changes)
## Release notes detail     (### <Feature>, then one description line, then one source line)
## Topic: TASK: <title> (NEW)      or  CONCEPT ... (UPDATE)
### File / ### Why / ### Shortdesc / ### Prerequisites / ### Context / ### Steps / ### Result / ### Example
   (a line starting with "→ " under Steps is a result or info line, not a step)
## No reference topic       (why no reference topic is needed)
## Technical detail         (### AC Layer ... , one paragraph each)
## Behaviour notes          (bullets)
```
Mark anything you cannot confirm as `[SME NEEDED] ...` (add `BLOCKER` if the draft cannot ship without it).

## Step 4: dry run, then decide
Run without `--docx`/`--out` first:
`python3 -m docaidev run <key> --repo <paths> --ref <key> --accuracy <n> --observations observations.json --draft draft.md --docs <published docs folder> --app-url <url> --seed seed.json`
Read the conflicts and the scope check (NEW vs UPDATE). Show the writer each conflict and which
source won. If the ranking is wrong for this team, pass `--precedence live,walkthrough,repo,tracker` reordered.

## Step 5: build the review document
Add `--meta meta.json --style style.json --docx <path>`. The tool asks for a write confirmation:
tell the writer the exact phrase `write <path>` and let them type it (or pass it as `--confirm`
only after they have).

## Step 6: the SME review loop
When reviewers return comments, ask the writer to tag every one: `changed`, `already_changed` or
`ignored` (an ignored comment needs a reason). Save them as `reviews.json`
(`[{"id": "R1", "comment": "...", "disposition": "changed"}]`) and pass `--reviews`. The run stops
(exit 3) listing any untagged comment. Fix the draft for `changed` items, then re-run.

## What the document contains
Four parts: metadata; release notes (prose and a detail table); draft topics with inline source
tags (`[SOURCE CONFIRMED]`, `[CORRECTION]`); author notes (technical detail, behaviour notes,
SME-n/PM-n open items, scan and changes tables, validation table, checklists, screenshots).
Margin comments come from two authors: `Phase3-Generate` (source-based) and `Phase4-Quality`
(style guide from `style.json`).

## Exit codes
0 done; 1 input or environment error; 2 paused at the accuracy gate; 3 review threads unresolved;
4 write not confirmed.

## Rules
- Only write inside the output folder the writer named; ask before writing anywhere else.
- Every claim must trace to a source: tracker, code, tests, live app, or the writer.
- Report limits plainly: a missing environment check, an untested adapter, or an unrendered
  Word file are things to say, not to hide.
- Tell the writer when a run was a dry run and nothing was written.
