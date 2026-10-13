"""Phase 4 quality check: run a configurable style guide over drafted text and produce margin
comments in the form '[Category]. Rule: ... Issue: ... Suggested: ...'.

The rules are mechanical, so they run the same way every time. The style guide is data
(style.json): swap it for a company's own. Rules implemented:
  spelling variants, banned step openers, release-note sentence length, serial comma,
  exact-case UI labels, sentence-case section names, and consistency with evidence
  (draft text that reuses wording the evidence overruled)."""
import json
import re

STYLE, STRUCTURE, TERMINOLOGY, CONSISTENCY, RELEASE_NOTES, GRAMMAR = (
    "Style", "Structure", "Terminology", "Consistency", "Release notes", "Grammar")


def load_style(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def comment(category, rule, issue, suggested):
    return "[%s]. Rule: %s. Issue: %s Suggested: %s" % (category, rule, issue, suggested)


def check_line(text, kind, style, ui_labels=(), overruled=(), confirmed=(), pm_topics=()):
    """ui_labels: [(label, suffix)]. confirmed: values the evidence confirmed (so an overruled value that is
    only a fragment of a confirmed one is not flagged). pm_topics: code-only facts needing a PM call."""
    """kind: step | rn | body | shortdesc. Returns a list of comment strings."""
    out, snippet = [], text if len(text) <= 70 else text[:67] + "..."
    for bad, good in (style.get("spelling") or {}).items():
        if re.search(r"\b%s\b" % re.escape(bad), text, re.I):
            out.append(comment(STYLE, "house spelling '%s'" % good, "'%s' uses '%s'." % (snippet, bad), "use '%s'." % good))
    if kind == "step":
        for opener in style.get("banned_step_openers", []):
            if text.lower().startswith(opener.lower()):
                out.append(comment(STYLE, "imperative verbs in steps; avoid '%s'" % opener,
                                   "Step starts with '%s'." % opener, "start with a plain verb such as 'Open' or 'Select'."))
    limit = style.get("max_rn_sentence_words")
    if kind == "rn" and limit:
        for sent in re.split(r"(?<=[.!?])\s+", text):
            if len(sent.split()) > limit:
                out.append(comment(RELEASE_NOTES, "release notes sentence length (max %d words)" % limit,
                                   "'%s' has %d words." % (sent[:60] + "...", len(sent.split())), "split it into two sentences."))
    if style.get("serial_comma"):
        m = re.search(r"\b\w+, \w+ (?:and|or) \w+", text)
        if m:
            out.append(comment(GRAMMAR, "serial (Oxford) comma in lists of three or more",
                               "'%s' has no comma before the last item." % m.group(0), "add a comma before 'and' or 'or'."))
    for label, suffix in ui_labels:   # suffix lets a label like 'Ports' match only as 'Ports tab', not the plain word
        for m in re.finditer(r"\b%s%s\b" % (re.escape(label), re.escape(suffix)), text, re.I):
            if m.group(0) != label + suffix:
                out.append(comment(TERMINOLOGY, "exact-case UI label '%s'" % label,
                                   "text has '%s'." % m.group(0), "write it exactly as '%s'." % (label + suffix)))
                break
    stripped = text
    for good in sorted(confirmed, key=len, reverse=True):
        stripped = re.sub(re.escape(good), " ", stripped, flags=re.I)
    for old in overruled:
        if old and re.search(r"\b%s\b" % re.escape(old), stripped, re.I):
            out.append(comment(CONSISTENCY, "consistency with the evidence",
                               "text uses '%s', wording the ticket used but the evidence overruled." % old,
                               "use the label confirmed on screen."))
    if text.lstrip().startswith("[SME NEEDED"):
        out.append(comment("SME NEEDED", "unconfirmed claim", "'%s' has no confirming source." % snippet,
                           "confirm with the SME before publishing."))
    for topic in pm_topics:
        if re.search(r"\b%s\b" % re.escape(topic), text, re.I):
            out.append(comment("PM DECISION NEEDED", "code-only detail", "'%s' is defined in code but absent from the ticket and the screen." % topic,
                               "decide whether it is user-facing and belongs in the documentation."))
    return out


def check_heading(name, style):
    """Section names should be sentence case: only the first word capitalised."""
    if style.get("heading_case") != "sentence":
        return []
    words = name.split()
    if any(w[:1].isupper() and not w.isupper() for w in words[1:]):
        return [comment(STRUCTURE, "sentence-case section names", "'%s' is in title case." % name,
                        "use '%s'." % (name[:1] + name[1:].lower()))]
    return []
