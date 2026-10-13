"""End-to-end flow: fetch -> accuracy gate -> repo scan -> findings -> reconcile -> draft ->
review gate -> confirmed write. Every human decision can be given as a flag (repeatable demos,
tests) or asked interactively."""
import json
import os
import sys
import tempfile

from . import config
from .adapters import AdapterError, get_adapter
from .extract import facts_from_acceptance_criteria, facts_from_code, load_observations, load_reviews
from .gates import WriteConfirmation, accuracy_gate, unresolved_threads
from .capture import CaptureError, capture
from . import corpus, quality
from .output import render_markdown
from .report import build as build_report
from .reconcile import ConsistencyThread, Finding, Reconciler
from .repo import RepoAdapter, RepoError

DEFAULT_PRECEDENCE = ["live", "walkthrough", "repo", "tracker"]


def _ask(question, preset, out):
    if preset is not None:
        out("%s %s" % (question, preset))
        return preset
    if sys.stdin.isatty():
        return input(question + " ")
    raise SystemExit("Needs an answer for: %s (pass the matching flag)" % question)


def run(a, out=print):
    cfg = config.load() or {}
    tracker = a.tracker or cfg.get("tracker", "paste")
    out("== 1. Fetch (%s) ==" % tracker)
    item = get_adapter(tracker, cfg.get("settings", {})).fetch(a.key)
    out("%s: %s" % (item.key, item.title))
    missing = [n for n, c in item.coverage().items() if not c["found"]]
    for n, c in item.coverage().items():
        out("  %-20s %s" % (n, "found" if c["found"] else "MISSING" + (" (essential)" if c["essential"] else "")))

    out("\n== 2. Accuracy gate ==")
    choice = _ask("Rate the tracker data: 1 complete, 2 incomplete, 3 inaccurate, 4 pause.", a.accuracy, out)
    gate = accuracy_gate(choice, "tracker", [m for m in missing if m in ("acceptance_criteria", "linked_changes")])
    out("-> " + gate.message)
    if not gate.proceed:
        return 2

    out("\n== 3. Repo scan ==")
    thread, findings = ConsistencyThread(), []
    repos = RepoAdapter(a.repo or cfg.get("repos", []))
    for path, ok, msg in repos.check():
        out("  %s %s (%s)" % ("ok  " if ok else "FAIL", path, msg))
    if not all(ok for _, ok, _ in repos.check()):
        out("A configured repo is missing; fix the path and re-run.")
        return 1
    ref_key = a.ref or item.key
    refs = repos.references(ref_key)
    tests = repos.tests_for(ref_key)
    out("  files mentioning %s: %d, of which tests: %d" % (
        ref_key, sum(len(v) for v in refs.values()), sum(len(v) for v in tests.values())))

    cap = None
    if getattr(a, "app_url", None) and getattr(a, "seed", None):
        out("\n== 4. Environment check (seed, read the screen, screenshot, clean up) ==")
        try:
            with open(a.seed, encoding="utf-8") as fh:
                recipe = json.load(fh)
            cap = capture(a.app_url, recipe, "DOC_SEED_" + ref_key, tempfile.mkdtemp(prefix="docaidev-shots-"),
                          allow_remote=getattr(a, "allow_remote_seed", False), log=lambda m: out(m))
            if cap.error:
                out("  capture problem: " + cap.error)
        except (CaptureError, OSError, ValueError, KeyError) as e:
            out("ERROR: environment check failed: %s" % e)
            return 1

    def feed(batch):
        for f in batch:
            for prior in thread.add(f):
                out("  CONFLICT on '%s': %s says \"%s\" but %s says \"%s\"" % (
                    f.topic, prior.source, prior.value, f.source, f.value))
            findings.append(f)

    out("\n== 5. Findings and conflicts ==")
    try:
        for repo, files in refs.items():
            for rel in files:
                feed(facts_from_code(repos.read(repo, rel)))
        feed(facts_from_acceptance_criteria(item.acceptance_criteria, "tracker"))
        if a.observations:
            feed(load_observations(a.observations))
        if cap:
            feed([Finding(o["topic"], o["value"], o["source"]) for o in cap.observations])
    except (RepoError, ValueError, OSError) as e:
        out("ERROR: %s" % e)
        return 1
    out("  %d findings, %d topics in conflict" % (len(findings), len(thread.conflicts())))

    out("\n== 6. Reconcile ==")
    order = a.precedence.split(",") if a.precedence else DEFAULT_PRECEDENCE
    excluded = list(gate.excluded_sources) + (a.exclude.split(",") if a.exclude else [])
    resolutions = Reconciler(order, excluded).resolve(findings)
    out("  precedence: %s%s" % (" > ".join(order), "   excluded: " + ", ".join(excluded) if excluded else ""))

    scan, draft_text = None, None
    if getattr(a, "draft", None):
        with open(os.path.expanduser(a.draft), encoding="utf-8") as fh:
            draft_text = fh.read()
    if getattr(a, "docs", None):
        from .ac import topics as _topics
        scan = corpus.scan(corpus.load(a.docs), getattr(a, "docs_url", None) or "https://docs.example.com",
                           _topics(draft_text or item.description), resolutions, item.key)
        out("  docs scan: %d findings, %d scope mismatches" % (len(scan["rows"]), len(scan["mismatch"])))
        for m in scan["mismatch"]:
            out("  MISMATCH: " + m)

    threads = load_reviews(a.reviews) if a.reviews else []
    out("\n== 7. Review gate (no silent skips) ==")
    blocked = unresolved_threads(threads)
    for t, why in blocked:
        out("  BLOCKED thread %s: %s" % (t.id, why))
    if blocked:
        out("Resolve the threads above, then re-run.")
        return 3
    out("  %d review threads, all resolved" % len(threads))

    draft = render_markdown(item.title or item.key, resolutions, threads)
    out("\n== 8. Draft ==\n" + draft)
    targets = [("md", a.out)] if a.out else []
    if getattr(a, "docx", None):
        targets.append(("docx", a.docx))
    if not targets:
        out("(no --out or --docx given; nothing written)")
        return 0
    presets = a.confirm if isinstance(a.confirm, list) else ([a.confirm] if a.confirm else [])
    wc = WriteConfirmation()
    for kind, target in targets:
        phrase = wc.phrase(target)
        typed = next((c for c in presets if c.strip().lower() == phrase.lower()), presets[0] if presets else None)
        typed = _ask("Type '%s' to write the file:" % phrase, typed, out)
        if not wc.confirm(target, typed):
            out("Not confirmed; nothing written to %s." % target)
            return 4
        path = os.path.expanduser(target)
        if kind == "md":
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(draft)
        else:
            meta = {}
            if getattr(a, "meta", None):
                with open(os.path.expanduser(a.meta), encoding="utf-8") as fh:
                    meta = json.load(fh)
            build_report({"item": item, "resolutions": resolutions, "threads": threads, "capture": cap,
                          "repos": repos.paths, "references": refs, "tests": tests, "meta": meta,
                          "draft": draft_text, "scan": scan,
                          "style": quality.load_style(getattr(a, "style", None))}).save(path)
        out("Wrote " + target)
    return 0
