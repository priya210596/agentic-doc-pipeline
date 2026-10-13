"""Deterministic fact extraction for the runnable demo. In a real run Claude reads tickets, code
and the live app and produces findings; this module defines the plain conventions the demo uses
and validates anything handed to the reconciler."""
import json
import re

from .reconcile import Finding

CODE_FACT = re.compile(r"doc-fact:\s*(?P<topic>[^=]+?)\s*=\s*(?P<value>.+?)\s*$")
AC_FACT = re.compile(r"^(?P<topic>[^:]{2,60}):\s*(?P<value>.+)$")


def facts_from_acceptance_criteria(criteria, source="tracker"):
    """'Ports tab label: Ports' -> Finding. Lines without 'topic: value' are skipped."""
    out = []
    for line in criteria:
        m = AC_FACT.match(line.strip())
        if m:
            out.append(Finding(m.group("topic").strip(), m.group("value").strip(), source))
    return out


def facts_from_code(text, source="repo"):
    out = []
    for line in text.splitlines():
        m = CODE_FACT.search(line)
        if m:
            out.append(Finding(m.group("topic").strip(), m.group("value").strip(), source))
    return out


def load_observations(path):
    """Observations recorded from a live app or walkthrough: [{topic, value, source}, ...]."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list):
        raise ValueError("observations file must be a JSON list")
    out = []
    for i, o in enumerate(raw):
        missing = [k for k in ("topic", "value", "source") if not str(o.get(k, "")).strip()]
        if missing:
            raise ValueError("observation %d is missing: %s" % (i, ", ".join(missing)))
        out.append(Finding(str(o["topic"]).strip(), str(o["value"]).strip(), str(o["source"]).strip()))
    return out


def load_reviews(path):
    from .gates import ReviewThread
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return [ReviewThread(str(r["id"]), r.get("comment", ""), r.get("disposition", ""), r.get("reason", "")) for r in raw]
