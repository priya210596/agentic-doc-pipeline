"""Gate logic as plain functions. The skill asks the human; these decide what the answer means,
so the rules are testable and not buried in prompt text."""
from dataclasses import dataclass, field
from typing import List

ACCURACY_CHOICES = {
    "1": "complete", "2": "incomplete", "3": "inaccurate", "4": "pause",
    "complete": "complete", "incomplete": "incomplete", "inaccurate": "inaccurate", "pause": "pause",
}


@dataclass
class GateOutcome:
    proceed: bool
    excluded_sources: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    message: str = ""


def accuracy_gate(choice, tracker_name="tracker", missing_fields=()):
    """Source-trust gate: the writer rates what was fetched from the tracker."""
    c = ACCURACY_CHOICES.get(str(choice).strip().lower())
    if c is None:
        raise ValueError("Choose 1-4 (complete / incomplete / inaccurate / pause)")
    if c == "complete":
        return GateOutcome(True, message="proceeding with %s data" % tracker_name)
    if c == "incomplete":
        return GateOutcome(True, flags=["UNCONFIRMED:" + m for m in missing_fields],
                           message="proceeding; missing items marked UNCONFIRMED")
    if c == "inaccurate":
        return GateOutcome(True, excluded_sources=[tracker_name],
                           message="%s excluded; other sources are authoritative" % tracker_name)
    return GateOutcome(False, message="paused until the tracker is updated")


DISPOSITIONS = ("changed", "already_changed", "ignored")


@dataclass
class ReviewThread:
    id: str
    comment: str
    disposition: str = ""   # one of DISPOSITIONS
    reason: str = ""


def unresolved_threads(threads):
    """No-silent-skip gate. Returns threads that block the pipeline: untagged, invalid tag,
    or 'ignored' without a written reason."""
    bad = []
    for t in threads:
        if t.disposition not in DISPOSITIONS:
            bad.append((t, "no disposition"))
        elif t.disposition == "ignored" and not t.reason.strip():
            bad.append((t, "ignored without a reason"))
    return bad


class WriteConfirmation:
    """Explicit-write-confirmation gate: a write is allowed only after the exact phrase for
    that target is given. Approval for one target never covers another."""

    def __init__(self):
        self._approved = set()

    @staticmethod
    def phrase(target):
        return "write %s" % target

    def confirm(self, target, typed):
        if typed.strip().lower() == self.phrase(target).lower():
            self._approved.add(target)
            return True
        return False

    def allowed(self, target):
        return target in self._approved
