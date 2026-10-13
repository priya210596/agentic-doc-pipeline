"""Jira Cloud adapter over REST. Credentials come from environment variables, never from config files."""
import base64
import json
import os
import urllib.error
import urllib.request

from ..ac import extract_acceptance_criteria
from ..schema import LinkedChange, WorkItem
from .base import Adapter, AdapterError


def _adf_to_text(node):
    """Flatten Atlassian Document Format to plain text, keeping list items on their own lines."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    kind = node.get("type")
    if kind == "text":
        return node.get("text", "")
    inner = "".join(_adf_to_text(c) for c in node.get("content", []))
    if kind == "listItem":
        return "- " + inner.strip() + "\n"
    if kind in ("paragraph", "heading"):
        return inner + "\n"
    return inner


class JiraAdapter(Adapter):
    name = "jira"

    def _conf(self):
        base = (self.settings.get("base_url") or "").rstrip("/")
        email, token = os.environ.get("JIRA_EMAIL"), os.environ.get("JIRA_API_TOKEN")
        if not (base and email and token):
            raise AdapterError("Jira needs base_url in config plus JIRA_EMAIL and JIRA_API_TOKEN environment variables.")
        auth = base64.b64encode(("%s:%s" % (email, token)).encode()).decode()
        return base, {"Authorization": "Basic " + auth, "Accept": "application/json"}

    def _get(self, path):
        base, headers = self._conf()
        req = urllib.request.Request(base + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise AdapterError("Jira %s returned HTTP %s" % (path, e.code))
        except urllib.error.URLError as e:
            raise AdapterError("Cannot reach Jira: %s" % e.reason)

    def test_connection(self):
        try:
            me = self._get("/rest/api/3/myself")
            return True, "Connected as %s" % me.get("displayName", "unknown")
        except AdapterError as e:
            return False, str(e)

    def fetch(self, key):
        ac_field = self.settings.get("acceptance_criteria_field")  # e.g. customfield_10040
        data = self._get("/rest/api/3/issue/%s?expand=renderedFields&fields=*all" % key)
        f = data["fields"]
        desc = _adf_to_text(f.get("description"))
        ac = []
        if ac_field and f.get(ac_field):
            raw = f[ac_field]
            text = _adf_to_text(raw) if isinstance(raw, dict) else str(raw)
            ac = [l.lstrip("-* ").strip() for l in text.splitlines() if l.strip()]
        if not ac:
            ac = extract_acceptance_criteria(desc)
        item = WorkItem(
            key=data["key"], source=self.name, title=f.get("summary", ""), description=desc,
            state=(f.get("status") or {}).get("name", ""), url="%s/browse/%s" % (self.settings["base_url"].rstrip("/"), data["key"]),
            acceptance_criteria=ac,
            parent=(f.get("parent") or {}).get("key"),
            children=[s["key"] for s in f.get("subtasks", [])],
            discussion=[_adf_to_text(c.get("body")) for c in (f.get("comment") or {}).get("comments", [])],
        )
        try:
            dev = self._get("/rest/dev-status/latest/issue/detail?issueId=%s&applicationType=GitHub&dataType=pullrequest" % data["id"])
            for d in dev.get("detail", []):
                for pr in d.get("pullRequests", []):
                    item.linked_changes.append(LinkedChange(ref=pr.get("id", ""), title=pr.get("name", ""), url=pr.get("url", "")))
        except AdapterError:
            pass  # dev panel not enabled; coverage report will show linked_changes missing
        return item
