"""Fallback for any company: the writer supplies a spec as a text or markdown file."""
import os
import re

from ..ac import extract_acceptance_criteria
from ..schema import WorkItem
from .base import Adapter, AdapterError


class PasteAdapter(Adapter):
    name = "paste"

    def test_connection(self):
        return True, "No connection needed; pass a path to a spec file as the key"

    def fetch(self, key):
        path = os.path.expanduser(key)
        if not os.path.isfile(path):
            raise AdapterError("Spec file not found: %s" % path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        first = next((l.lstrip("# ").strip() for l in text.splitlines() if l.strip()), os.path.basename(path))
        m = re.match(r"\s*([A-Za-z][A-Za-z0-9]*-\d+)\b", first)
        return WorkItem(key=m.group(1) if m else os.path.basename(path), source=self.name, title=first, description=text,
                        acceptance_criteria=extract_acceptance_criteria(text))
