"""DocCorpusAdapter: scan an existing docs folder (Markdown) to decide, per topic, whether a page
already exists (UPDATE) or not (NEW), and to find stale text that contradicts the evidence."""
import os
import re


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def load(docs_dir):
    pages = []
    for dirpath, dirs, files in os.walk(os.path.expanduser(docs_dir)):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            with open(full, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            title = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), name)
            pages.append({"file": os.path.relpath(full, docs_dir), "title": title, "lines": lines})
    return pages


def _sections(page):
    """Yield (section heading, line) for every non-empty body line."""
    head = page["title"]
    for l in page["lines"]:
        if l.startswith("#"):
            head = l.lstrip("# ").strip()
        elif l.strip():
            yield head, l.strip()


def scan(pages, base_url, topics, resolutions, story):
    url = lambda p: base_url.rstrip("/") + "/" + os.path.splitext(p["file"])[0]
    rows, changes, status, mismatch = [], [], {}, []
    for t in topics:
        page = next((p for p in pages if _norm(p["title"]) == _norm(t["title"])), None)
        status[t["title"]] = ("PUBLISHED PAGE EXISTS: " + url(page)) if page else "NO PUBLISHED PAGE: new topic"
        rows.append([url(page) if page else "--", page["file"] if page else "(none)", "--",
                     "Page exists." if page else "No page with this title.", "docs scan",
                     "YES: UPDATE" if page else "YES: NEW TOPIC"])
        if page and t["scope"] == "NEW":
            mismatch.append("Draft says NEW for \"%s\" but a published page already exists (%s)." % (t["title"], page["file"]))
        if not page and t["scope"] == "UPDATE":
            mismatch.append("Draft says UPDATE for \"%s\" but no published page has that title." % t["title"])
    # One finding per stale sentence: apply every correction that matches it, so the row shows the final text.
    stale = {}   # (file, section, line) -> [new text, [(old, new)], page]
    for r in resolutions:
        for old in r.overruled.values():
            pat = r"\b%s\b" % re.escape(old)
            for p in pages:
                for head, line in _sections(p):
                    if re.search(pat, line):
                        entry = stale.setdefault((p["file"], head, line), [line, [], p])
                        entry[0] = re.sub(pat, r.value, entry[0])
                        entry[1].append((old, r.value))
    for (fname, head, line), (new, pairs, p) in stale.items():
        fixes = ", ".join("\"%s\" to \"%s\"" % pr for pr in pairs)
        rows.append([url(p), fname, head, "Page says \"%s\"; evidence requires: %s." % (line, fixes), "docs scan", "YES"])
        changes.append([fname, head, line, new, story, "OPEN"])
    return {"rows": rows, "changes": changes, "status": status, "mismatch": mismatch}
