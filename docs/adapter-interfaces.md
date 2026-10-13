# Adapter Interfaces

Every adapter satisfies a narrow contract so the orchestrator and consistency thread never need to know which concrete system is behind it. All adapters return the same shape:

```
AdapterResult = {
  content:     <the actual data — text, record, file contents>
  metadata:    { sourceId, retrievedAt, sourceType }
  confidence:  HIGH | MEDIUM | LOW    // how much the adapter itself trusts this data
}
```

Below are the 5 adapter types the pipeline needs, their required methods, and example real-world systems each could wrap.

---

## 1. TrackerAdapter

**Purpose:** pull the *stated intent* of a change — what a ticket/work-item says should happen.

```
TrackerAdapter {
  getItem(itemId) -> AdapterResult<{ title, description, acceptanceCriteria, linkedCommits }>
  getLinkedItems(itemId) -> AdapterResult<Item[]>       // e.g. child stories under an epic
  getLinkedCode(itemId) -> AdapterResult<CommitRef[]>   // commit/PR references, if the tracker exposes them
}
```

**Example implementations:** a Jira adapter (REST API v3), a Linear adapter (GraphQL API), a GitHub Issues adapter (REST/GraphQL), an Azure DevOps Boards adapter.

---

## 2. RepoAdapter

**Purpose:** pull the *ground truth* of what was actually built — code the tracker's description doesn't capture (edge cases, exact field names, guard conditions).

```
RepoAdapter {
  getDiff(ref) -> AdapterResult<{ files: FileDiff[] }>
  getFile(path, ref) -> AdapterResult<{ contents }>
  grep(pattern, scope) -> AdapterResult<Match[]>
}
```

**Example implementations:** a local-git-clone adapter (shells out to `git show`/`git diff` against a repo the pipeline has on disk), a GitHub/GitLab REST API adapter (reads a branch directly without requiring a local clone — removes the "did you `git fetch`?" failure mode), a Bitbucket API adapter.

---

## 3. LiveEnvAdapter

**Purpose:** confirm what's *actually deployed and observable right now* — often a subset of what the ticket or code diff describes, since not everything ships together.

```
LiveEnvAdapter {
  listEnvironments() -> AdapterResult<EnvRef[]>          // never hardcode a target — always enumerate
  query(envRef, resourceQuery) -> AdapterResult<Record[]>
  getFeatureState(envRef, flagKey) -> AdapterResult<{ enabled, config }>
}
```

**Example implementations:** a REST-API adapter against a staging environment's admin endpoints, a direct (read-only) database query adapter, a feature-flag service adapter (LaunchDarkly, Unleash, a homegrown flags table).

---

## 4. DocCorpusAdapter

**Purpose:** find everywhere in the *existing* documentation a change might already be described, so drafting decides UPDATE vs. CREATE-NEW correctly instead of guessing.

```
DocCorpusAdapter {
  search(query, scope) -> AdapterResult<DocMatch[]>       // full-text search across the whole corpus
  getTopic(topicId) -> AdapterResult<{ content, structure }>
  listRelated(topicId) -> AdapterResult<TopicRef[]>        // e.g. resolve cross-references/transclusions
}
```

**Example implementations:** a local-filesystem adapter that greps a Markdown or DITA source tree directly (fast, complete — the recommended default), a Git-backed docs-repo adapter (same idea, over a remote repo via API instead of a local clone), a headless-CMS adapter (Contentful, Sanity) for teams whose docs live in a CMS rather than as files, with a live-site adapter as a fallback only when local source access is unavailable or ambiguous.

---

## 5. OutputAdapter

**Purpose:** produce the actual deliverable, and carry the review-resolution loop (see `gate-taxonomy.md` — review-acceptance gate) in whatever medium the team's reviewers already work in.

```
OutputAdapter {
  generate(draft) -> AdapterResult<{ fileRef | pageRef }>
  addAnnotation(fileRef, location, tag, note) -> void      // attach a confidence/provenance tag
  listOpenAnnotations(fileRef) -> AdapterResult<Annotation[]>
  resolveAnnotation(fileRef, annotationId, disposition) -> void
}
```

**Example implementations:** a Word-document adapter (margin comments carry the tags reviewers accept/reject), a pull-request adapter (the draft is a Markdown diff, tags become PR review comments), a Confluence-page adapter (inline comments), a Notion-page adapter (block comments).

---

## Why the contract is this narrow

Every method above takes an identifier and returns data plus a confidence signal — nothing adapter-specific leaks into the return shape. That's deliberate: the orchestrator, consistency thread, and reconciler are written once against `AdapterResult`, and adding support for a new tracker, repo host, or CMS is purely a matter of implementing one of these five interfaces against a new backend — no change to any other part of the pipeline.
