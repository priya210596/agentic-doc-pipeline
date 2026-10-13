"""OutputAdapter (Markdown): every claim carries its provenance tag; nothing is asserted bare."""

BADGE = {"CONFIRMED": "[CONFIRMED]", "NEEDS REVIEW": "[NEEDS REVIEW]", "ASSUMED": "[ASSUMED]"}


def render_markdown(title, resolutions, threads=()):
    lines = ["# " + title, ""]
    for r in resolutions:
        lines.append("- %s **%s:** %s  _(source: %s)_" % (BADGE[r.confidence], r.topic, r.value, r.winner))
        for src, val in sorted(r.overruled.items()):
            lines.append("  - %s said \"%s\"; %s" % (src, val, r.reason))
    if threads:
        lines += ["", "## Review log", ""]
        for t in threads:
            lines.append("- %s: %s -> %s%s" % (t.id, t.comment, t.disposition or "UNRESOLVED",
                                                " (%s)" % t.reason if t.reason else ""))
    return "\n".join(lines) + "\n"
