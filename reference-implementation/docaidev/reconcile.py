"""Consistency thread + reconciler.

Findings arrive from any source. The thread flags a conflict the moment two sources give
different values for the same topic. The reconciler then applies a precedence order that the
team declared once, and records which source won so the choice is auditable.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List

CONFIRMED, NEEDS_REVIEW, ASSUMED = "CONFIRMED", "NEEDS REVIEW", "ASSUMED"


def _norm(v):
    return re.sub(r"\s+", " ", str(v)).strip().casefold()


@dataclass
class Finding:
    topic: str        # what is being claimed about, e.g. "Export button label"
    value: str        # what the source says
    source: str       # "live", "walkthrough", "repo", "tracker", ...


@dataclass
class Resolution:
    topic: str
    value: str
    winner: str
    confidence: str
    supporting: List[str] = field(default_factory=list)
    overruled: Dict[str, str] = field(default_factory=dict)   # source -> value it gave
    reason: str = ""


class ConsistencyThread:
    """Collects findings and reports conflicts as they appear, not at draft time."""

    def __init__(self):
        self.findings = []  # type: List[Finding]

    def add(self, finding):
        """Add a finding; return the earlier findings it conflicts with (empty if none)."""
        clash = [f for f in self.findings if f.topic == finding.topic
                 and f.source != finding.source and _norm(f.value) != _norm(finding.value)]
        self.findings.append(finding)
        return clash

    def conflicts(self):
        by_topic = {}
        for f in self.findings:
            by_topic.setdefault(f.topic, []).append(f)
        return {t: fs for t, fs in by_topic.items() if len({_norm(f.value) for f in fs}) > 1}


class Reconciler:
    def __init__(self, precedence, excluded=()):
        """precedence: sources from most to least trusted. excluded: sources ignored for this run."""
        if len(set(precedence)) != len(precedence):
            raise ValueError("precedence contains duplicate sources")
        self.precedence = list(precedence)
        self.excluded = set(excluded)

    def _rank(self, source):
        # A source nobody ranked is least trusted, never silently trusted.
        return self.precedence.index(source) if source in self.precedence else len(self.precedence)

    def resolve(self, findings):
        by_topic = {}
        for f in findings:
            by_topic.setdefault(f.topic, []).append(f)
        return [self._resolve_topic(t, fs) for t, fs in by_topic.items()]

    def _resolve_topic(self, topic, fs):
        usable = [f for f in fs if f.source not in self.excluded]
        if not usable:
            f = sorted(fs, key=lambda x: self._rank(x.source))[0]
            return Resolution(topic, f.value, f.source, ASSUMED, [f.source], {},
                              "only excluded sources reported this")
        usable.sort(key=lambda x: self._rank(x.source))
        best = usable[0]
        agree = sorted({f.source for f in usable if _norm(f.value) == _norm(best.value)}, key=self._rank)
        over = {f.source: f.value for f in usable if _norm(f.value) != _norm(best.value)}
        if over:
            return Resolution(topic, best.value, best.source, NEEDS_REVIEW, agree, over,
                              "%s outranks %s in the declared order" % (best.source, ", ".join(sorted(over))))
        if len(agree) >= 2:
            return Resolution(topic, best.value, best.source, CONFIRMED, agree, {}, "sources agree")
        top = self.precedence[0] if self.precedence else None
        conf = CONFIRMED if best.source == top else NEEDS_REVIEW
        return Resolution(topic, best.value, best.source, conf, agree, {}, "single source: %s" % best.source)
