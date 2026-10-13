"""RepoAdapter: read ground truth from local git clones. Read-only; never writes to a repo."""
import os
import subprocess

TEST_HINTS = ("test", "tests", "spec", "specs", "__tests__", "e2e", "cypress", "playwright")
MAX_READ = 200_000


class RepoError(Exception):
    pass


def _git(repo, args):
    p = subprocess.run(["git", "-C", repo] + args, capture_output=True, text=True, timeout=60)
    if p.returncode not in (0, 1):  # git grep exits 1 for "no matches"
        raise RepoError("git %s failed in %s: %s" % (args[0], repo, p.stderr.strip()))
    return p.stdout


def _walk_grep(root, term):
    hits = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for name in files:
            full = os.path.join(dirpath, name)
            try:
                with open(full, encoding="utf-8") as fh:
                    if term in fh.read(MAX_READ):
                        hits.append(os.path.relpath(full, root))
            except (UnicodeDecodeError, OSError):
                continue  # binary or unreadable
    return sorted(hits)


def is_test_path(path):
    parts = path.lower().replace("\\", "/").split("/")
    name = parts[-1]
    return any(p in TEST_HINTS for p in parts[:-1]) or any(h in name for h in ("test_", "_test.", ".test.", ".spec.", "_spec."))


class RepoAdapter:
    def __init__(self, paths):
        self.paths = [os.path.abspath(os.path.expanduser(p)) for p in paths]

    def check(self):
        """Return [(path, ok, message)] for pre-flight."""
        out = []
        for p in self.paths:
            if not os.path.isdir(p):
                out.append((p, False, "directory not found"))
            elif not os.path.isdir(os.path.join(p, ".git")):
                out.append((p, True, "plain directory (no git history; changed_files unavailable)"))
            else:
                out.append((p, True, "ok"))
        return out

    def changed_files(self, repo, base, head="HEAD"):
        """Files changed between two refs (three-dot: changes on head since it diverged from base)."""
        out = _git(self._resolve(repo), ["diff", "--name-only", "%s...%s" % (base, head)])
        return [l for l in out.splitlines() if l]

    def references(self, term, repos=None):
        """Every tracked file mentioning `term` (e.g. a ticket key). Returns {repo: [paths]}."""
        found = {}
        for repo in (repos or self.paths):
            root = self._resolve(repo)
            if os.path.isdir(os.path.join(root, ".git")):
                hits = [l for l in _git(root, ["grep", "-l", "-F", "--", term]).splitlines() if l]
            else:
                hits = _walk_grep(root, term)
            if hits:
                found[repo] = hits
        return found

    def tests_for(self, key, repos=None):
        """Test files that mention the ticket key; this is how tests link back to a feature."""
        return {r: [f for f in files if is_test_path(f)] for r, files in self.references(key, repos).items()
                if any(is_test_path(f) for f in files)}

    def read(self, repo, rel):
        """Read one file. Refuses paths that escape the repo and truncates very large files."""
        root = self._resolve(repo)
        full = os.path.realpath(os.path.join(root, rel))
        if not (full == root or full.startswith(root + os.sep)):
            raise RepoError("Refusing to read outside the repository: %s" % rel)
        if not os.path.isfile(full):
            raise RepoError("No such file: %s" % rel)
        with open(full, encoding="utf-8", errors="replace") as fh:
            data = fh.read(MAX_READ + 1)
        return data[:MAX_READ] + ("\n[truncated]" if len(data) > MAX_READ else "")

    def _resolve(self, repo):
        full = os.path.realpath(os.path.expanduser(repo))
        if full not in [os.path.realpath(p) for p in self.paths]:
            raise RepoError("Repo is not in the configured list: %s" % repo)
        return full
