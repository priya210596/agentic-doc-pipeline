import argparse
import json
import sys

from . import config
from .adapters import REGISTRY, AdapterError, get_adapter
from .run import run as run_flow


def cmd_setup(a):
    settings = {k: v for k, v in (("repo", a.repo), ("base_url", a.base_url),
                                  ("acceptance_criteria_field", a.ac_field)) if v}
    cfg = {"tracker": a.tracker, "settings": settings, "repos": a.repos or [], "style_guide": a.style_guide}
    ok, msg = get_adapter(a.tracker, settings).test_connection()
    print(("OK  " if ok else "FAIL") + " " + a.tracker + ": " + msg)
    if not ok and not a.force:
        print("Not saved. Fix the connection, or pass --force to save anyway.")
        return 1
    print("Saved to", config.save(cfg))
    return 0


def _adapter(a):
    cfg = config.load()
    if not cfg:
        print("No config found. Run: doc-aidev setup --tracker <name>")
        return None
    return get_adapter(a.tracker or cfg["tracker"], cfg.get("settings", {}))


def cmd_test(a):
    ad = _adapter(a)
    if not ad:
        return 1
    ok, msg = ad.test_connection()
    print(("OK  " if ok else "FAIL") + " " + ad.name + ": " + msg)
    return 0 if ok else 1


def cmd_fetch(a):
    ad = _adapter(a)
    if not ad:
        return 1
    try:
        item = ad.fetch(a.key)
    except AdapterError as e:
        print("ERROR:", e)
        return 1
    if a.json:
        print(json.dumps(item.to_dict(), indent=2))
    else:
        print("%s [%s] %s" % (item.key, item.state or "-", item.title))
        for name, c in item.coverage().items():
            mark = "found  " if c["found"] else "MISSING"
            print("  %s %s%s" % (mark, name, "  (essential)" if c["essential"] and not c["found"] else ""))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="doc-aidev")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--tracker", required=True, choices=sorted(REGISTRY))
    s.add_argument("--repo"); s.add_argument("--base-url"); s.add_argument("--ac-field")
    s.add_argument("--repos", nargs="*"); s.add_argument("--style-guide"); s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_setup)
    t = sub.add_parser("test"); t.add_argument("--tracker"); t.set_defaults(fn=cmd_test)
    f = sub.add_parser("fetch"); f.add_argument("key"); f.add_argument("--tracker"); f.add_argument("--json", action="store_true")
    f.set_defaults(fn=cmd_fetch)
    r = sub.add_parser("run", help="end-to-end flow on one work item")
    r.add_argument("key"); r.add_argument("--tracker"); r.add_argument("--repo", nargs="*")
    r.add_argument("--ref", help="string to find in code and tests (defaults to the key)")
    r.add_argument("--accuracy"); r.add_argument("--observations"); r.add_argument("--reviews")
    r.add_argument("--precedence"); r.add_argument("--exclude"); r.add_argument("--out"); r.add_argument("--confirm", action="append")
    r.add_argument("--docx", help="write the Word review document here")
    r.add_argument("--meta", help="metadata JSON (product, release, author, ...)"); r.add_argument("--draft", help="drafted content (Markdown)")
    r.add_argument("--style", help="style guide JSON for the quality check")
    r.add_argument("--docs", help="folder of existing published docs (Markdown) to scan"); r.add_argument("--docs-url", help="base URL for those docs")
    r.add_argument("--app-url", help="running app to seed and screenshot (localhost only)"); r.add_argument("--seed", help="seed recipe JSON")
    r.add_argument("--allow-remote-seed", action="store_true", help="allow seeding a non-localhost app (writes data there)")
    r.set_defaults(fn=lambda a: run_flow(a))
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
