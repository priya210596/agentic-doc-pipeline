"""Seed -> read the live screen -> screenshot -> cleanup.

Creates clearly tagged records, reads facts (labels, columns, options) straight from the running
page, captures screenshots, then deletes the records and verifies nothing tagged is left. Cleanup
always runs, even if the browser step fails. Only localhost targets are allowed unless the caller
opts in, because this writes to the app."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import List

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class CaptureError(Exception):
    pass


@dataclass
class CaptureResult:
    tag: str
    app_url: str
    shots: List[dict] = field(default_factory=list)          # {file, caption, page}
    seeded: List[dict] = field(default_factory=list)         # {resource, id, label}
    observations: List[dict] = field(default_factory=list)   # {topic, value, source:"live"}
    removed: int = 0
    leftovers: int = -1                                       # -1 = not verified
    error: str = ""

    @property
    def clean(self):
        return self.leftovers == 0 and self.removed == len(self.seeded)


def _http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, None
    except urllib.error.URLError as e:
        raise CaptureError("cannot reach %s: %s" % (url, e.reason))


def _text(el):
    return " ".join((el.text_content() or "").split())


def capture(app_url, recipe, tag, out_dir, allow_remote=False, log=print):
    host = urllib.parse.urlparse(app_url).hostname or ""
    if host not in LOCAL_HOSTS and not allow_remote:
        raise CaptureError("refusing to seed data into %s (not localhost); pass allow_remote=True to override" % host)
    base = app_url.rstrip("/")
    res = CaptureResult(tag=tag, app_url=base)
    resources = recipe["resources"]
    os.makedirs(out_dir, exist_ok=True)
    try:
        for rs in resources:
            for rec in rs["records"]:
                payload = dict(rec); payload[rs.get("tag_field", "note")] = tag
                status, body = _http("POST", base + rs["create_path"], payload)
                if status not in (200, 201) or not body:
                    raise CaptureError("seeding %s failed with HTTP %s" % (rs["name"], status))
                res.seeded.append({"resource": rs["name"], "id": str(body["id"]), "label": str(rec.get(rs.get("label_field", "id"), ""))})
        log("  seeded %d records tagged %s" % (len(res.seeded), tag))
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise CaptureError("playwright is not installed (pip install playwright && playwright install chromium)")
        timeout = recipe.get("timeout_ms", 15000)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": recipe.get("width", 1000), "height": recipe.get("height", 420)})
                    first = recipe["shots"][0]
                    page.goto(base + first.get("page", "/"))
                    page.wait_for_selector(first.get("wait_selector", "body"), timeout=timeout)
                    for ob in recipe.get("observe", []):
                        els = page.query_selector_all(ob["selector"])
                        if not els:
                            log("  observe: nothing found for '%s'" % ob["topic"])
                            continue
                        value = ", ".join(_text(e) for e in els) if ob.get("join_all") else _text(els[0])
                        res.observations.append({"topic": ob["topic"], "value": value, "source": "live"})
                    log("  read %d facts from the live screen" % len(res.observations))
                    for shot in recipe["shots"]:
                        page.goto(base + shot.get("page", "/"))
                        if shot.get("click"):
                            page.click(shot["click"], timeout=timeout)
                        page.wait_for_selector(shot.get("wait_selector", "body"), timeout=timeout)
                        path = os.path.join(out_dir, "%s.png" % shot.get("file", "screen"))
                        page.screenshot(path=path)
                        rows = len(page.query_selector_all(shot["rows_selector"])) if shot.get("rows_selector") else None
                        tab = _text(page.query_selector(shot["tab_selector"])) if shot.get("tab_selector") else ""
                        columns = ", ".join(_text(e) for e in page.query_selector_all(shot["columns_selector"])) if shot.get("columns_selector") else ""
                        workspace = _text(page.query_selector(shot["workspace_selector"])) if shot.get("workspace_selector") else ""
                        res.shots.append({"file": path, "caption": shot.get("caption", ""), "page": shot.get("page", "/"),
                                          "record": shot.get("record", ""), "rows": rows, "tab": tab, "columns": columns,
                                          "workspace": workspace, "resource": shot.get("resource", "")})
                        log("  captured " + os.path.basename(path))
                finally:
                    browser.close()
        except Exception as e:  # browser failures must not skip cleanup or crash the caller
            raise CaptureError("screenshot failed: %s" % str(e).splitlines()[0])
    except CaptureError as e:
        res.error = str(e)
    finally:
        by_name = {r["name"]: r for r in resources}
        for rec in reversed(res.seeded):  # newest first, so children go before parents
            status, _ = _http("DELETE", base + by_name[rec["resource"]]["delete_path"].format(id=rec["id"]))
            if status in (200, 204):
                res.removed += 1
        left, verified = 0, True
        for rs in resources:
            status, listing = _http("GET", base + rs["list_path"])
            if status != 200:
                verified = False
            else:
                left += sum(1 for r in (listing or []) if tag in json.dumps(r))
        res.leftovers = left if verified else -1
        log("  removed %d/%d seeded records; leftovers: %s" % (res.removed, len(res.seeded), res.leftovers))
    return res
