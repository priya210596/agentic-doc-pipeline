# Gate Taxonomy

The adapters and reconciler make the pipeline *portable*. These eight gate patterns are what make it *trustworthy* — they're the actual reusable design, independent of any tech stack. Each one is a recurring answer to "what happens when the pipeline needs a human decision it can't make itself."

---

### 1. Source-trust gate

**Problem it solves:** not every evidence source is reliable every time — a tracker item can be stale, mis-scoped, or simply wrong by the time work ships. Using it anyway silently poisons everything downstream.

**Pattern:** after pulling from a source, force an explicit judgment: is this source complete / incomplete / inaccurate for this change? If inaccurate, exclude it entirely from the reconciler rather than letting it quietly outvote better evidence.

**Generic example:** a pipeline pulls a ticket's acceptance criteria, then asks the reviewer to confirm accuracy before using it. The reviewer flags that the ticket describes a feature that was scoped down before shipping — the ticket is excluded, and a human walkthrough becomes the authoritative source for that item instead.

---

### 2. Blocking-input gate

**Problem it solves:** some evidence can only come from a human (e.g. "show me how this actually works"), and drafting without it produces confident-sounding guesses. But blocking forever if that input never arrives stalls the whole pipeline.

**Pattern:** hard-stop the dependent phase until the input is supplied — but always offer an explicit "I don't have this" escape that downgrades confidence on the affected items instead of blocking indefinitely.

**Generic example:** the pipeline requires a walkthrough recording before drafting UI-facing text. If none exists, the writer selects "no walkthrough available" — the pipeline proceeds, but every UI label in the draft is tagged NEEDS REVIEW instead of being asserted as fact.

---

### 3. Selection gate

**Problem it solves:** hardcoding a target (an environment, a branch, an instance) silently goes stale the moment that target changes, and the failure is invisible until someone notices the docs describe the wrong thing.

**Pattern:** enumerate live options and require an explicit pick every run, rather than assuming a default.

**Generic example:** before querying a live environment, the pipeline calls `listEnvironments()` and requires the operator to choose one from that list — it never falls back to "whatever was used last time."

---

### 4. Decision gate

**Problem it solves:** some routing decisions are genuinely ambiguous from evidence alone and have real downstream consequences (what gets built, published, or skipped) — guessing wrong wastes the whole downstream run.

**Pattern:** present the mutually exclusive options explicitly and require a pick before continuing, rather than picking the most likely one automatically.

**Generic example:** after reconciling all evidence for a change, the pipeline asks: does this warrant a new doc page, an update to an existing one, or both? The answer changes what phase 3 (draft generation) actually produces.

---

### 5. Dependency-enforcement gate

**Problem it solves:** a later phase can silently produce wrong output if it assumes an earlier phase ran, when it didn't (e.g. drafting content before checking whether it already exists elsewhere).

**Pattern:** a phase checks, at its own entry point, that its prerequisite phase actually completed — and refuses to run if it didn't, rather than trusting the orchestrator's order alone.

**Generic example:** the draft-generation phase checks for a completed doc-corpus scan result before running. If none exists, it refuses to start rather than risk creating a duplicate page for content that already exists elsewhere in the corpus.

---

### 6. Review-acceptance gate

**Problem it solves:** generated drafts contain both solid and shaky claims; asking a reviewer to catch every issue by reading prose start-to-finish is slow and error-prone.

**Pattern:** attach every claim as a discrete, taggable annotation (not just plain text) so a reviewer can accept or reject each one individually, in whatever medium they already review in.

**Generic example:** a draft is delivered as a document with inline comments, one per uncertain claim, each pre-labeled with why it's uncertain (e.g. "source conflict — tracker says X, live environment shows Y"). The reviewer responds to each comment rather than re-deriving the whole document's accuracy from scratch.

---

### 7. No-silent-skip gate

**Problem it solves:** open questions and flagged items are useless if they can be quietly ignored — a pipeline that "mostly" resolves its open items isn't actually trustworthy, because nobody can tell which ones were dropped.

**Pattern:** require every flagged item to carry an explicit disposition (resolved / rejected / intentionally deferred with a logged reason) before the phase is considered complete. An unresolved item blocks completion; it cannot just be left blank.

**Generic example:** before a reviewed document moves to the next phase, the pipeline checks that every comment thread has one of three tags applied. Any untagged thread blocks the phase — there is no path that lets a comment simply age out unaddressed.

---

### 8. Explicit-write-confirmation gate

**Problem it solves:** the pipeline's most dangerous action is usually its last one — writing the final result into a system of record (a live doc repo, a published page). An automated pipeline that does this without a distinct confirmation step turns "draft looks good" into "already published" by accident.

**Pattern:** separate "the content is approved" from "commit the write" into two distinct steps, with the write step requiring its own explicit confirmation — never bundled into a general "continue" action, and never triggered automatically just because upstream gates cleared.

**Generic example:** after a draft is fully reviewed and approved, the pipeline still asks, as a separate step, "write these N files to the live doc repository now?" before performing the write — approval of content and authorization to publish are never the same click.
