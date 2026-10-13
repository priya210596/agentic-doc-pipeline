# Agentic Documentation Pipeline — A Company-Agnostic Architecture

A generalized architecture for AI-powered, human-in-the-loop product documentation. It accelerates drafting by gathering and reconciling evidence automatically, while writers and reviewers stay in control at every decision point. It keeps documentation synchronized with what a team actually ships, and is abstracted from a production pipeline I built and run in a professional setting.

This repo contains no code tied to a specific company, tracker, or platform. It documents the *shape* of the system: an orchestrator, a set of pluggable evidence adapters, a conflict-resolution layer, and a chain of human decision gates. The intent is that any team — regardless of what ticketing tool, code host, or doc format they use — can implement the same shape against their own stack.

## The Problem

Documentation drifts out of sync with reality because the evidence a writer needs is scattered across systems that don't talk to each other:

- A ticket/work-item describes *intent*, but tickets go stale, get scoped down, or are wrong by the time work ships.
- A demo or walkthrough shows *actual behavior*, but only if someone remembers to record one.
- The codebase has the *ground truth* of what was built, but reading a diff cold rarely tells you what a user-facing change looks like.
- A live/staging environment shows what's *actually deployed*, which is often a subset of what the ticket described.
- The existing doc corpus already has related content that the change may or may not conflict with — nobody has time to grep all of it, every time.

A writer reconciling all five of these by hand, per change, is slow and error-prone. The system either isn't reconciled at all (docs silently go stale) or gets reconciled inconsistently (whoever's writing that day decides which source to trust).

## The Core Idea

Instead of one writer holding all of this in their head, the pipeline externalizes it into five stages:

1. **Orchestrator** — a single entry point that knows the fixed phase order and enforces gates between phases. It doesn't gather evidence itself; it delegates.
2. **Adapters** — one per evidence source (tracker, repo, live environment, doc corpus, output format). Each adapter has a narrow, swappable interface — see `docs/adapter-interfaces.md`. Swapping Jira for Linear, or a local git clone for a GitHub API call, means writing a new adapter, not touching the orchestrator.
3. **Consistency thread** — a cross-cutting check that runs after every adapter call, diffing new findings against everything gathered so far and flagging contradictions immediately, rather than discovering them while drafting.
4. **Reconciler** — applies a *declared* source-precedence order (e.g. "what's actually deployed" always outranks "what the ticket said") to resolve any conflicts the consistency thread flagged. The order is a config decision per team, not an ad hoc judgment call made per document.
5. **Draft generator + review-resolution loop** — produces output with every claim tagged by confidence/provenance, then routes it through a gated human review where every open question must be explicitly resolved — never silently dropped.

See `docs/architecture.md` for the full flow diagram.

## Why This Generalizes

Nothing about this shape assumes a specific company or platform:

- The adapter interfaces are defined by their *contract* (what a `fetch()` call returns), not by any particular vendor's API — see `docs/adapter-interfaces.md` for concrete swap-in examples (Jira vs. Linear vs. GitHub Issues; local git vs. a REST API; Word-doc-with-comments vs. a PR with a Markdown diff).
- The eight gate patterns in `docs/gate-taxonomy.md` are process patterns, not code — they're as applicable to a manual checklist as to a fully automated pipeline.
- The source-precedence idea (rank your evidence sources once, apply the ranking mechanically every time) works for any domain where multiple systems can disagree about the truth — not just software documentation.

What's specific to any one implementation is just which adapters you plug in and how you rank them. That's a config decision, not an architecture change.

## What's In This Repo

| Path | Contents |
|---|---|
| `docs/architecture.md` | End-to-end flow: orchestrator, adapters, consistency thread, reconciler, draft generator, review loop |
| `docs/adapter-interfaces.md` | Interface contracts for the 5 adapter types, with real-world implementation examples |
| `docs/gate-taxonomy.md` | The 8 reusable human-decision-gate patterns, with generic examples |
| `docs/case-study-enterprise-pipeline.md` | Architecture-level case study of the production pipeline this was abstracted from |
| `reference-implementation/` | Working open-source code for the tracker layer (GitHub, Jira, paste-a-spec), standard library only |

## Reference implementation status

`reference-implementation/` is a clean-room prototype, written without any code from the
production system. It implements the **TrackerAdapter** contract and reports which fields were
actually found, so a writer sees gaps before drafting.

| Component | Status |
|---|---|
| End-to-end `run` command: fetch, accuracy gate, repo scan, reconcile, review gate, docs scan, screenshot capture, Word review document, confirmed write | Working on a fictional example (`examples/rack-manager`, sample output included) |
| TrackerAdapter: GitHub, paste-a-spec | Working, tested |
| TrackerAdapter: Jira | Written, **not yet tested against a live site** |
| RepoAdapter (changed files, ticket references, linked tests, safe read) | Working, tested |
| Consistency thread and reconciler (declared precedence, exclusions, provenance tags) | Working, tested |
| Gates: accuracy, no-silent-skip, explicit-write-confirmation | Working, wired into `run` |
| Quality check (Phase 4): configurable style guide producing margin comments by category | Working, tested; rules are mechanical, not a language model |
| OutputAdapter: Markdown with per-claim provenance; Word document with real margin comments in four categories | Working, tested (Word file checked structurally, not opened in Word) |
| Environment capture: seed tagged records, read facts off the live screen, screenshot with Playwright, delete and verify (localhost only by default) | Working, tested |
| Fact extraction from tickets, code and the live app | Demo uses plain conventions; a real run uses an AI model to produce the same findings |
| DocCorpusAdapter (local Markdown docs: new-versus-update, stale-text detection) | Working, tested; reads local Markdown only |
| Reading comments back from a real review document, MCP wrapper | Not yet built |

Try it: `cd reference-implementation && sh examples/rack-manager/run_demo.sh`

Dependencies: the code uses only the Python standard library; Playwright and `gh` are optional. See [reference-implementation/README.md](reference-implementation/README.md#dependencies).

Run the tests: `cd reference-implementation && python3 -m unittest discover -s tests`
