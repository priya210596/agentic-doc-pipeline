"""Builds the review document in the production pipeline's four-part structure.
Page 1 metadata | Page 2 release notes (2a prose, 2b detail table) | Page 3 draft topics |
Page 4 author notes (not for publication).

Computed from evidence: metadata, topic status, inline source tags, SME/PM items and checklists,
scan and changes tables, validation table, screenshot tables, and every margin comment
(Phase3-Generate: source-based; Phase4-Quality: style guide).
Supplied as draft text (what an AI model would write): release-note and topic prose, technical
detail, behaviour notes. {Placeholders} in it are filled from reconciled findings."""
import os
import re

from .ac import blocks, section_items, topics as parse_topics
from .docx_writer import Doc
from .extract import AC_FACT
from . import quality

SOURCE_CONFIRMED, CORRECTION, SME_NEEDED, PM_DECISION = "SOURCE CONFIRMED", "CORRECTION", "SME NEEDED", "PM DECISION NEEDED"
GREEN, YELLOW, GREY, RED = "E2EFDA", "FFF2CC", "7F7F7F", "C00000"
P3, P4 = "Phase3-Generate", "Phase4-Quality"


def comment_for(r):
    """Pick the margin-comment category and text from a reconciler resolution."""
    if r.overruled and "tracker" in r.overruled:
        return CORRECTION, ("[CORRECTION]. Detail: the ticket says \"%s\"; %s shows \"%s\". "
                            "Question: update the ticket so the record agrees?" % (r.overruled["tracker"], r.winner, r.value))
    if r.overruled:
        return SME_NEEDED, "[SME NEEDED]. Detail: sources disagree (%s). Question: which is right?" % r.reason
    if len(r.supporting) >= 2:
        return SOURCE_CONFIRMED, "[SOURCE CONFIRMED]. Detail: %s agree on \"%s\"." % (" and ".join(r.supporting), r.value)
    if r.supporting == ["repo"]:
        return PM_DECISION, ("[PM DECISION NEEDED]. Detail: the code defines \"%s\" = \"%s\" but no ticket or live check mentions it. "
                             "Question: is this user-facing and worth documenting?" % (r.topic, r.value))
    return SME_NEEDED, "[SME NEEDED]. Detail: only %s reports \"%s\". Question: can you confirm it?" % (r.winner, r.value)


def inline_tag(r):
    cat = comment_for(r)[0]
    if cat == CORRECTION:
        return "[CORRECTION: ticket said \"%s\"; %s shows \"%s\"]" % (r.overruled["tracker"], r.winner, r.value)
    if cat == SOURCE_CONFIRMED:
        return "[SOURCE CONFIRMED: %s \"%s\", %s agree]" % (r.topic, r.value, " + ".join(r.supporting))
    return "[%s: %s \"%s\" from %s]" % (cat, r.topic, r.value, r.winner)


def _strip_key(title, key):
    return re.sub(r"^\s*[A-Za-z]+-\d+\s*[:\-]\s*", "", title or key).strip() or key


def _fill(text, by_topic):
    """Replace {Topic} placeholders with resolved values; return (text, [resolutions used], [missing])."""
    used, missing = [], []

    def sub(m):
        r = by_topic.get(m.group(1).strip().lower())
        if r:
            used.append(r)
            return r.value
        missing.append(m.group(1))
        return "[UNRESOLVED: %s]" % m.group(1)
    return re.sub(r"\{([^}]+)\}", sub, text), used, missing


class _Ctx:
    """State shared while drafting lines: lookups, style guide, and the SME items found on the way."""
    def __init__(self, by_topic, style, res):
        self.by_topic, self.style = by_topic, style
        self.unresolved, self.sme_lines = [], []
        self.labels = []
        for entry in style.get("ui_label_topics", []):
            topic, suffix = (entry, "") if isinstance(entry, str) else entry
            if topic.lower() in by_topic:
                self.labels.append((by_topic[topic.lower()].value, suffix))
        self.overruled = sorted({v for r in res for v in r.overruled.values()})
        self.confirmed = [r.value for r in res]
        self.pm_topics = [r.topic for r in res if r.supporting == ["repo"] and not r.overruled]


def _line(d, text, c, kind="body", numbered=None, bullet=False):
    """Write one drafted line: fill placeholders, add an inline source tag, and margin comments."""
    text, used, missing = _fill(text, c.by_topic)
    c.unresolved += missing
    comments = []
    if missing:
        comments.append((P3, "[SME NEEDED]. Detail: no confirmed value for %s. Question: what should this say?" % ", ".join(missing)))
    elif used:
        comments.append((P3, comment_for(used[0])[1]))
    comments += [(P4, q) for q in quality.check_line(text, kind, c.style, c.labels, c.overruled, c.confirmed, c.pm_topics)]
    flagged = text.lstrip().startswith("[SME NEEDED") or bool(missing)
    if text.lstrip().startswith("[SME NEEDED"):
        c.sme_lines.append(text)
    prefix = ("%d. " % numbered) if numbered else ("• " if bullet else "")
    runs = [(prefix + text, {"color": RED} if flagged else {})]
    if used and not flagged:
        runs.append(("  " + inline_tag(used[0]), {"color": GREY, "italic": True}))
    d.para(runs, comment=comments or None)


def build(ctx):
    item, res, cap = ctx["item"], ctx["resolutions"], ctx.get("capture")
    meta, scan, th = ctx.get("meta") or {}, ctx.get("scan"), ctx.get("threads", [])
    by_topic = {r.topic.lower(): r for r in res}
    title = _strip_key(item.title, item.key)
    draft = ctx.get("draft") or item.description
    c = _Ctx(by_topic, ctx.get("style") or {}, res)
    tps = parse_topics(draft)
    if not tps:  # no Topic blocks anywhere: fall back to one task topic from the ticket
        secs = [(n.title(), section_items(item.description, (n,))) for n in ("prerequisites", "steps", "result")]
        tps = [{"kind": "TASK", "title": title, "scope": "NEW", "sections": [x for x in secs if x[1]]}]
    scope = " + ".join(sorted({t["scope"] for t in tps}, reverse=True))
    inst = meta.get("instance_name", "environment")
    d = Doc(author=P3, date=ctx.get("date", "2026-01-01T00:00:00Z"))

    # ---- Page 1: metadata ------------------------------------------------
    d.banner_table(meta.get("product", "DOCUMENTATION DRAFT"), fill="1F4E79")
    d.heading("%s — %s" % (item.key, title), 1)
    d.para("%s release  |  Author: %s  |  Date: %s" % (meta.get("release", "--"), meta.get("author", "--"), meta.get("date", "--")), color=GREY)
    env = "not checked"
    if cap:
        warn = "" if (cap.clean and not cap.error) else "  ⚠ " + (cap.error or "cleanup not verified")
        env = "%s (%s) — %d records seeded, %d removed, %s left behind%s" % (
            inst, cap.app_url, len(cap.seeded), cap.removed, cap.leftovers if cap.leftovers >= 0 else "unknown", warn)
    d.table([["Field", "Value"], ["Story", "%s (%s)" % (item.key, item.source)], ["Epic", meta.get("epic", "--")],
             ["Sprint", meta.get("sprint", "--")], ["SME", meta.get("sme", "--")], ["Story author", meta.get("story_author", "--")],
             ["Instance verified", env], ["Scope", scope], ["Status", "READY FOR SME REVIEW"]], widths=[2400, 6600])
    d.page_break()

    # ---- Page 2: release notes ---------------------------------------------
    d.banner_table("DESTINATION: What's New / Release notes", fill="1F4E79")
    d.heading("Section 2a — Release notes content", 2)
    entries = blocks(draft, "Release notes") or [("Highlights", ["You can now %s." % (title[:1].lower() + title[1:])])]
    for name, lines in entries:
        d.para("RELEASE NOTES — %s | NEW" % name, bold=True)
        for ln in lines:
            _line(d, ln, c, kind="rn")
    d.heading("Section 2b — Release notes detail table (SME review)", 2)
    rows = [["Feature", "Description", "Source"]]
    detail = blocks(draft, "Release notes detail")
    for feat, lines in detail:
        desc, used, miss = _fill(lines[0] if lines else "", by_topic)
        c.unresolved += miss
        src = _fill(lines[1], by_topic)[0] if len(lines) > 1 else "--"
        cm = [(P3, comment_for(used[0])[1])] if used else None
        rows.append([(feat, {"bold": True, "comment": cm}), desc, src])
    if not detail:
        rows += [[(r.topic, {"bold": True, "comment": (P3, comment_for(r)[1])}), r.value, "%s (%s)" % (r.winner, r.confidence)] for r in res]
    d.table(rows, widths=[2600, 4000, 2400])
    d.page_break()

    # ---- Page 3: draft topics ----------------------------------------------
    d.banner_table("DRAFT TOPIC CONTENT — FOR REVIEW", fill="375623")
    d.para("Topic set derived from Phase 1 findings:", bold=True)
    for i, t in enumerate(tps, 1):
        sec = {n.lower(): ls for n, ls in t["sections"]}
        d.para("%d. %s — %s   FILE: %s" % (i, t["kind"], t["title"], (sec.get("file") or ["--"])[0]), bold=True)
        if sec.get("why"):
            d.para("• Why: " + " ".join(sec["why"]))
    nref = blocks(draft, "No reference topic")
    if nref:
        d.para("%d. No reference topic — %s" % (len(tps) + 1, " ".join(l for _, ls in nref for l in ls)), bold=True)
    for i, t in enumerate(tps, 1):
        sec = {n.lower(): ls for n, ls in t["sections"]}
        d.heading("TOPIC %d — %s (%s)" % (i, t["kind"] + (": " + t["title"] if t["kind"] != "CONCEPT" else ""),
                                              "UPDATE existing draft" if t["scope"] == "UPDATE" else t["scope"]), 2)
        d.para("File: %s" % (sec.get("file") or ["--"])[0])
        st = (scan["status"].get(t["title"]) if scan else None) or "docs scan not run"
        if st.startswith("PUBLISHED PAGE EXISTS: "):
            d.para("Status: LOCAL DRAFT EXISTS — live page exists at:")
            d.para(st.split(": ", 1)[1], color="0563C1")
        else:
            d.para("Status: %s" % st.replace("NO PUBLISHED PAGE: ", "NO PUBLISHED PAGE — "))
        d.para("─" * 70, color=GREY)
        d.para("TITLE: %s" % t["title"], bold=True)
        if sec.get("shortdesc"):
            _line(d, "SHORTDESC: " + " ".join(sec["shortdesc"]), c, kind="shortdesc")
        for name, lines in t["sections"]:
            if name.lower() in ("file", "why", "shortdesc"):
                continue
            hc = [(P4, q) for q in quality.check_heading(name, c.style)]
            d.para(name, bold=True, comment=hc or None)
            n = 0
            for ln in lines:
                if name.lower() == "steps" and not ln.startswith("→"):
                    n += 1
                    _line(d, ln, c, kind="step", numbered=n)
                else:
                    _line(d, ln, c, bullet=name.lower() in ("key benefits", "considerations", "how it works", "prerequisites")
                          and not ln.startswith(("[", "Note")))
    d.page_break()

    # ---- SME / PM items (collected from the whole analysis) -----------------
    no_evidence = [a for a in item.acceptance_criteria
                   if not (AC_FACT.match(a.strip()) and AC_FACT.match(a.strip()).group("topic").strip().lower() in by_topic)]
    sme = []  # (description, blocker)
    for line in c.sme_lines:
        sme.append((re.sub(r"^\[SME NEEDED[^\]]*\]\s*", "", line), "BLOCKER" in line.split("]")[0]))
    sme += [("Confirm \"%s\" = \"%s\" (%s)." % (r.topic, r.value, r.reason), False)
            for r in res if r.confidence == "NEEDS REVIEW" and r.supporting != ["repo"]]
    sme += [("No evidence for acceptance criterion \"%s\". Confirm it ships, or drop it from the ticket." % a, False) for a in no_evidence]
    sme += [("Placeholder {%s} has no confirmed value." % u, False) for u in sorted(set(c.unresolved))]
    if scan:
        sme += [(m, False) for m in scan["mismatch"]]
    pm = [(r.topic, "Defined in code as \"%s\"; not in the ticket or on screen. Document it or leave it out?" % r.value)
          for r in res if r.supporting == ["repo"] and not r.overruled]
    sid = lambda i, b: "SME-%d%s" % (i, " [BLOCKER]" if b else "")

    # ---- Page 4: author notes ----------------------------------------------
    d.banner_table("AUTHOR NOTES — NOT FOR PUBLICATION", fill="C00000")
    d.heading("Technical detail", 2)
    for name, lines in blocks(draft, "Technical detail"):
        d.para(name + ":", bold=True)
        d.para(" ".join(lines))
    d.para("Evidence per acceptance criterion:", bold=True)
    for n, ac in enumerate(item.acceptance_criteria, 1):
        m = AC_FACT.match(ac.strip())
        r = by_topic.get(m.group("topic").strip().lower()) if m else None
        if r:
            d.para("AC %d: %s — evidence from %s (%s)." % (n, ac, ", ".join(r.supporting + sorted(r.overruled)), r.confidence))
        else:
            d.para("AC %d: %s — NO EVIDENCE found in code, tests, or environment." % (n, ac), color=RED)
    refs, tests = ctx.get("references", {}), ctx.get("tests", {})
    d.para("Files mentioning %s: %s. Test files: %s." % (item.key, ", ".join(f for v in refs.values() for f in v) or "none",
                                                          ", ".join(f for v in tests.values() for f in v) or "none"))

    d.heading("Behaviour notes", 2)
    for name, lines in blocks(draft, "Behaviour notes"):
        for ln in lines:
            d.para("• " + ln)

    d.heading("Open items", 2)
    rows = [["Item", "Description"]] + [[sid(i, b), t] for i, (t, b) in enumerate(sme, 1)] + [["PM-%d" % i, "%s: %s" % p] for i, p in enumerate(pm, 1)]
    d.table(rows if len(rows) > 1 else rows + [["None", "--"]], widths=[1800, 7200])

    file_col = meta.get("file_column", "Doc file")
    d.heading(meta.get("scan_heading", "Section 1 — Published-docs scan findings"), 2)
    if scan:
        d.table([["#", "Page URL", file_col, "Section", "Finding", "Source", "Edit needed?"]] +
                [[str(i)] + r_ for i, r_ in enumerate(scan["rows"], 1)], widths=[400, 2000, 1500, 1100, 2300, 800, 900])
    else:
        d.para("Not run: no --docs folder was given, so new-versus-update is taken from the draft's own labels.", italic=True)

    d.heading(meta.get("changes_heading", "Section 2 — Changes required"), 2)
    body = []
    if scan:
        for t in tps:
            if t["scope"] == "NEW":
                files = [ls for n, ls in t["sections"] if n.lower() == "file"]
                body.append([files[0][0] if files else "--", "whole topic", "(none)", "Create topic: " + t["title"], item.key, "OPEN"])
        body += [list(x) for x in scan["changes"]]
    rows = [["#", file_col, "Section/field", "Current text", "Required change", "Story", "Status"]]
    rows += [[str(i)] + r_ for i, r_ in enumerate(body, 1)]
    d.table(rows if len(rows) > 1 else rows + [["--", "--", "--", "--", "--", item.key, "--"]], widths=[400, 1700, 1300, 2000, 2000, 800, 800])

    d.heading("Instance validation table", 2)
    rows = [["Record", meta.get("id_column", "Id / file"), "Status on %s" % inst]]
    for s_ in (cap.seeded if cap else []):
        rows.append(["%s — %s" % (s_["resource"], s_["label"]), s_["id"], "seeded, captured, removed" if cap.clean else "seeded — CHECK CLEANUP"])
    for repo, files in refs.items():
        for f in files:
            rows.append(["code — %s" % os.path.basename(f), f, "found in code (mentions %s)" % item.key])
    d.table(rows if len(rows) > 1 else rows + [["--", "--", "no environment or code check ran"]], widths=[3000, 3200, 2800])

    d.heading("SME checklist", 2)
    rows = [["Item", "Description", "Status"]] + [[sid(i, b), t, "OPEN"] for i, (t, b) in enumerate(sme, 1)]
    rows.append(["SME-all", "Read the whole draft and its inline tags against the product before publishing.", "OPEN"])
    d.table(rows, widths=[1800, 6000, 1200])

    d.heading("PM checklist", 2)
    rows = [["Item", "Detail", "Decision needed"]] + [["PM-%d" % i, p[0] + ": defined in code as \"%s\"" % by_topic[p[0].lower()].value, "Document it or leave it out?"]
                                                       for i, p in enumerate(pm, 1)]
    d.table(rows if len(rows) > 1 else rows + [["--", "Nothing outstanding", "--"]], widths=[1000, 5000, 3000])

    if cap and cap.shots:
        d.heading(meta.get("screenshot_heading", "Screenshot evidence — populated tabs (seeded)"), 2)
        d.para("All seeded records were deleted from %s after capture (tag %s, %d removed, %s left behind). "
               "Screenshots belong in author notes only; they are never placed in the reader-facing draft." % (
                   inst, cap.tag, cap.removed, cap.leftovers if cap.leftovers >= 0 else "unknown"), shade=GREEN)
        for k, sh in enumerate(cap.shots, 1):
            d.image(sh["file"], alt=sh["caption"])
            d.para("Screenshot %d — %s" % (k, sh["caption"]), bold=True)
            mine = [x for x in cap.seeded if x["resource"] == sh.get("resource")]
            d.table([["Field", "Value"], ["Instance", "%s (%s)" % (inst, cap.app_url)],
                     ["Test cases", "%s seed recipe" % item.key],
                     ["Seeded records", "%s tagged %s; removed after capture" % (
                         "%d %s" % (sh["rows"], sh.get("resource", "records")) if sh.get("rows") is not None else "records", cap.tag)],
                     ["Workspace", sh.get("workspace") or sh["page"]], ["Captured", meta.get("date", "--")]], widths=[2000, 7000])
            d.table([[(["What this confirms:",
                        "• Tab label shown on screen: \"%s\"" % (sh.get("tab") or "--"),
                        "• %s row%s listed" % (sh.get("rows", "?"), "" if sh.get("rows") == 1 else "s"),
                        "• Columns: %s" % (sh.get("columns") or "--")], {"fill": GREEN})]], header=False, widths=[9000])
    elif cap and cap.error:
        d.heading("Screenshot evidence", 2)
        d.para("Capture failed: %s" % cap.error, shade=YELLOW)

    if th:
        d.heading("Review log", 2)
        d.table([["Thread", "Comment", "Disposition"]] + [[t.id, t.comment, t.disposition + (" (%s)" % t.reason if t.reason else "")] for t in th],
                widths=[900, 5000, 3100])
    return d
