# doc-aidev (working name)

A tracker-agnostic source layer for documentation pipelines. Fetches a work item from
GitHub, Jira, or a pasted spec into one normalized shape, and reports which fields were
actually found so a writer can see the gaps before drafting.

Clean-room prototype. Standard library only (Python 3.9+).

## Try it
    python3 -m docaidev setup --tracker github --repo OWNER/REPO
    python3 -m docaidev fetch 123
    python3 -m unittest discover -s tests

Jira: set `JIRA_EMAIL` and `JIRA_API_TOKEN`, then
`setup --tracker jira --base-url https://yourco.atlassian.net --ac-field customfield_NNNNN`.
Secrets are read from the environment and never saved.

## Dependencies
- **The package imports only the Python standard library**, so nothing else needs installing for the core
  (fetching, reconciling, gates, docs scan, quality check, Word output).
- **`python-docx` is not needed.** The Word writer is built in; python-docx was used only to check the output while developing.
- **`gh` (GitHub CLI)** is needed only for the GitHub tracker.
- **Jira** needs two environment variables (`JIRA_EMAIL`, `JIRA_API_TOKEN`) and no installs.
- **`git`** is optional: plain folders work without it.
- **Playwright and Chromium** are needed only for screenshot capture (`sh install.sh` installs them).

## Requirements and install
| Needed for | What | How |
|---|---|---|
| Everything (core) | Python 3.9+ | none beyond Python: the package uses only the standard library |
| Screenshots (optional) | Playwright and Chromium | `sh install.sh` (or `pip install -r requirements.txt && python3 -m playwright install chromium`) |
| GitHub tracker (optional) | `gh` CLI, logged in | https://cli.github.com, then `gh auth login` |
| Jira tracker (optional) | `JIRA_EMAIL` and `JIRA_API_TOKEN` environment variables | none to install |
| Reading repo history (optional) | `git` | usually already present; plain folders work without it |

`sh install.sh` checks all of the above, installs what it can, and runs the tests.
`sh install.sh --no-browser` sets up the core only. Without Playwright, a run still completes and the
document says the screenshot capture failed.

## Run the end-to-end demo
A fictional "Rack Manager" app and a ticket with deliberate traps: wrong tab labels, a missing cable
option, an acceptance criterion with no evidence, and two details that exist only in code.
Needs Python 3.9+; screenshots need `pip install playwright && playwright install chromium`
(without it the run still works and the document notes the capture failed).

    sh examples/rack-manager/run_demo.sh

- **Run 1** shows the review gate blocking on untagged comments.
- **Run 2** resolves them, then:
  1. seeds eight tagged records (rack and cabinet ports and cables) into the demo app, **reads the labels, columns and options straight off the running screen** (these become the "live" facts), captures four screenshots, deletes the records and verifies none are left;
  2. scans a folder of existing published docs: which topics already have a page (UPDATE) or not (NEW), and which published sentences now contradict the evidence;
  3. reconciles all sources by declared precedence (live > walkthrough > repo > tracker);
  4. builds a **Word review document** in the production pipeline's four-part layout: metadata, release notes 2a/2b, three draft topics with inline source tags, author notes (technical detail, behaviour notes, SME-n / PM-n open items, scan and changes tables, validation table, SME and PM checklists, four screenshots each with a field table), and real margin comments from two authors: `Phase3-Generate` (source-based: CORRECTION, SOURCE CONFIRMED) and `Phase4-Quality` (a configurable style guide: Style, Structure, Terminology, Consistency, Release notes, Grammar, plus SME NEEDED and PM DECISION NEEDED);
  5. writes it only after an exact typed confirmation.

**The quality check.** `style.json` is a style guide as data (house spelling, banned step openers, release-note sentence length, serial comma, exact-case UI labels, sentence-case section names). The sample draft contains a few deliberate slips so you can see each rule fire; swap in another company's `style.json` to change the rules.

**What is computed and what is supplied.** Computed from evidence: every table, status, tag, comment, checklist, scan result and screenshot. Supplied as text in `draft.md`: the prose a model would write (release-note wording, topic text, technical detail, behaviour notes). `{Placeholders}` in that prose are filled from the reconciled findings, so a wrong ticket label never reaches the draft.

A pre-generated result is in `examples/rack-manager/sample-output/` (the `.docx` plus the run transcript).
Seeding is refused for any non-localhost app unless `--allow-remote-seed` is passed.

`doc-aidev run <key> --repo <paths> --ref <string> --accuracy 1 --observations f.json --reviews r.json
--app-url <url> --seed seed.json --meta meta.json --style style.json --draft draft.md --docs <docs folder> --docx out.docx --confirm "write out.docx"`. Any decision flag you omit is asked interactively.

## How findings get made (important)
The demo uses plain conventions so it runs without an AI: `Topic: value` lines in acceptance
criteria, `doc-fact: topic = value` comments in code, and a JSON file for live/walkthrough
observations. A real run has Claude read tickets, code, and the live app and produce the same
`{topic, value, source}` findings; the reconciler, gates and output code are identical either way.
Acceptance-criteria lines without a `topic: value` shape produce no finding.

## Status
- Done: schema, AC extraction, GitHub / Jira / paste adapters, repo adapter, consistency thread,
  reconciler, gate logic, Markdown output, local docs scan, seed-capture-cleanup screenshots (Playwright), Word
  output with real margin comments (standard library only), the `run` command, the example. 51 tests.
- The Word file is validated structurally (opens in python-docx, all XML parts parse, comments and image present).
  It has not been opened in Microsoft Word here.
- Jira adapter is untested against a live site.
- Not built: reading real comments back from a review document, MCP wrapper. The docs scan reads local Markdown only.
