"""GitHub adapter. Uses the `gh` CLI, so it needs no MCP server and no token handling here."""
import json
import re
import subprocess

from ..ac import extract_acceptance_criteria
from ..schema import LinkedChange, WorkItem
from .base import Adapter, AdapterError


def _gh(args):
    try:
        p = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise AdapterError("GitHub CLI 'gh' not found. Install it from https://cli.github.com and run 'gh auth login'.")
    if p.returncode != 0:
        raise AdapterError("gh %s failed: %s" % (" ".join(args[:2]), p.stderr.strip()))
    return p.stdout


class GitHubAdapter(Adapter):
    name = "github"

    def test_connection(self):
        try:
            _gh(["auth", "status"])
            return True, "gh is installed and authenticated"
        except AdapterError as e:
            return False, str(e)

    def _repo_args(self):
        repo = self.settings.get("repo")
        return ["--repo", repo] if repo else []

    def fetch(self, key):
        number = re.sub(r"\D", "", key)
        if not number:
            raise AdapterError("GitHub keys look like '123' or '#123', got '%s'" % key)
        fields = "number,title,body,state,url,comments,closedByPullRequestsReferences"
        data = json.loads(_gh(["issue", "view", number, "--json", fields] + self._repo_args()))
        body = data.get("body") or ""
        item = WorkItem(
            key=str(data["number"]), source=self.name, title=data.get("title", ""),
            description=body, state=data.get("state", ""), url=data.get("url", ""),
            acceptance_criteria=extract_acceptance_criteria(body),
            discussion=[c.get("body", "") for c in data.get("comments", [])],
        )
        for pr in data.get("closedByPullRequestsReferences", []) or []:
            item.linked_changes.append(self._pr(pr.get("number")))
        return item

    def _pr(self, number):
        raw = json.loads(_gh(["pr", "view", str(number), "--json", "number,title,url,files"] + self._repo_args()))
        try:
            diff = _gh(["pr", "diff", str(number)] + self._repo_args())
        except AdapterError:
            diff = ""
        return LinkedChange(ref=str(raw["number"]), title=raw.get("title", ""), url=raw.get("url", ""),
                            files=[f.get("path", "") for f in raw.get("files", [])], diff=diff)
