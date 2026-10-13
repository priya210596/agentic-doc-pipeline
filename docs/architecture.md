# Architecture

## End-to-end flow

```
┌───────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR                                                          │
│  Fixed phase order. Owns gate enforcement between phases.             │
│  Delegates all evidence-gathering to adapters — gathers nothing       │
│  itself.                                                               │
└───────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌───────────────────────────────────────────────────────────────────────┐
│  ADAPTERS  (pluggable, one per evidence source — see                  │
│             adapter-interfaces.md)                                    │
│                                                                         │
│   TrackerAdapter    ──  intent: what was the change supposed to do    │
│   RepoAdapter       ──  ground truth: what was actually built         │
│   LiveEnvAdapter    ──  what's actually deployed right now            │
│   DocCorpusAdapter  ──  what the existing docs already say            │
│   (human input)     ──  walkthrough / demo, no adapter — direct       │
│                         capture, treated as a first-class source      │
│                                                                         │
│  Each call returns: { content, metadata, confidence }                  │
└───────────────────────────────────┬───────────────────────────────────┘
                                     │  every result flows through
                                     ▼
┌───────────────────────────────────────────────────────────────────────┐
│  CONSISTENCY THREAD  (cross-cutting, runs after every adapter call)   │
│                                                                         │
│  Diffs each new finding against everything gathered so far.           │
│  Flags contradictions the moment they appear — not at draft time.     │
│  Produces a running CONFLICT list, tagged with which sources disagree. │
└───────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌───────────────────────────────────────────────────────────────────────┐
│  RECONCILER                                                            │
│                                                                         │
│  Applies a declared, per-team source-precedence order to every         │
│  flagged conflict — e.g.:                                             │
│    Live environment  >  Human walkthrough  >  Repo  >  Tracker        │
│  The order is configured once, not decided per document.              │
│  A source can also be excluded entirely (source-trust gate) if it's   │
│  been flagged as unreliable for this change.                          │
│                                                                         │
│  Output: a resolved finding set, each item tagged with its winning     │
│  source and confidence level.                                          │
└───────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌───────────────────────────────────────────────────────────────────────┐
│  DRAFT GENERATOR                                                       │
│                                                                         │
│  Produces the actual doc/output via an OutputAdapter.                  │
│  Every claim in the draft is tagged by provenance/confidence           │
│  (e.g. CONFIRMED / NEEDS REVIEW / ASSUMED) — nothing is asserted        │
│  without a traceable source.                                          │
└───────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌───────────────────────────────────────────────────────────────────────┐
│  REVIEW-RESOLUTION LOOP  (gated — see gate-taxonomy.md)                │
│                                                                         │
│  Human reviewer(s) respond to every tagged item.                       │
│  No-silent-skip gate: every open item must be explicitly resolved      │
│  (accepted / corrected / intentionally ignored with a reason) before   │
│  the pipeline considers the document done.                            │
└───────────────────────────────────────────────────────────────────────┘
```

## Stage responsibilities

**Orchestrator.** The only component that knows the full phase sequence. It calls adapters in order, checks that each phase's required gate has been cleared before invoking the next phase, and stops the pipeline cold if a gate is unresolved. It holds no domain logic about *what* is being documented — only *when* each step is allowed to run.

**Adapters.** Each adapter wraps exactly one external system behind a narrow, uniform contract (see `adapter-interfaces.md`). This is what makes the pipeline portable: the orchestrator and consistency thread never talk to a tracker, repo host, or environment API directly — they only ever call an adapter's methods. Swapping the underlying system means writing a new adapter that satisfies the same contract; nothing upstream changes.

**Consistency thread.** Runs continuously, not just at the end. As soon as two sources disagree — a tracker says a field is optional, a live environment shows it's required — that's flagged immediately, with both sources cited. This turns "the draft turned out wrong" into "we caught a source conflict before writing a word," which is the single biggest lever on draft accuracy.

**Reconciler.** Conflict resolution is mechanical, not a judgment call made fresh each time. A team declares its trust order once (typically: what's live and observable beats what a human said beats what the code shows beats what a ticket claims — but any order can be declared). The reconciler applies that order to every flagged conflict and records which source won and why, so the decision is auditable later.

**Draft generator.** Never asserts a claim without a source. Every sentence or field in the output carries a confidence tag derived from the reconciler's output, so a reviewer can tell at a glance what's solid and what needs a second look — instead of having to independently verify the entire document.

**Review-resolution loop.** The last human gate. Nothing in the draft is allowed to disappear silently — every flagged item gets an explicit disposition. This is what keeps the pipeline trustworthy over many runs: a reviewer never has to wonder whether an open question was actually handled or just dropped.
