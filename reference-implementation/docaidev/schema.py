"""Normalized work item. Every adapter returns this shape; pipeline phases read only this."""
from dataclasses import dataclass, field, asdict
from typing import List, Optional

# Fields the pipeline cannot run without vs. fields that degrade gracefully.
ESSENTIAL = ("title", "description", "acceptance_criteria", "linked_changes")
OPTIONAL = ("parent", "children", "discussion", "test_cases")


@dataclass
class LinkedChange:
    ref: str            # PR number, commit sha, MR id
    title: str = ""
    url: str = ""
    files: List[str] = field(default_factory=list)
    diff: str = ""      # may be empty; pipeline falls back to reading the local repo


@dataclass
class WorkItem:
    key: str
    source: str                          # adapter name, e.g. "github"
    title: str = ""
    description: str = ""
    state: str = ""
    url: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    discussion: List[str] = field(default_factory=list)
    linked_changes: List[LinkedChange] = field(default_factory=list)
    test_cases: List[str] = field(default_factory=list)

    def coverage(self):
        """Report which fields were found, so the accuracy gate can show real gaps."""
        report = {}
        for name in ESSENTIAL + OPTIONAL:
            report[name] = {"found": bool(getattr(self, name)), "essential": name in ESSENTIAL}
        return report

    def to_dict(self):
        return asdict(self)
