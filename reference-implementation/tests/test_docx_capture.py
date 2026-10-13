import argparse, importlib.util, json, os, re, struct, sys, tempfile, threading, unittest, zlib, zipfile
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from docaidev.capture import CaptureError, capture
from docaidev.docx_writer import Doc, png_size
from docaidev.reconcile import Resolution
from docaidev.report import comment_for, CORRECTION, SME_NEEDED, PM_DECISION, SOURCE_CONFIRMED
from docaidev.run import run

EX = os.path.join(os.path.dirname(__file__), "..", "examples", "rack-manager")
try:
    import playwright.sync_api  # noqa
    HAVE_PW = True
except ImportError:
    HAVE_PW = False


def tiny_png(path):
    raw = zlib.compress(b"\x00\xff\x00\x00")
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def start_app():
    spec = importlib.util.spec_from_file_location("demo_app", os.path.join(EX, "app", "server.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    srv = mod.serve(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def recipe(**kw):
    with open(os.path.join(EX, "seed.json")) as fh:
        r = json.load(fh)
    r.update(kw)
    return r


class WriterTests(unittest.TestCase):
    def test_package_is_valid_and_has_comments_table_image(self):
        d = tempfile.mkdtemp(); img = os.path.join(d, "t.png"); tiny_png(img)
        doc = Doc(); doc.heading("Title", 1); doc.para("Hello <&>", comment="[SME NEEDED]. check")
        doc.table([["A", "B"], [("x", {"comment": "c2"}), "y"]]); doc.image(img, alt="a \"quoted\" alt")
        out = os.path.join(d, "o.docx"); doc.save(out)
        z = zipfile.ZipFile(out)
        for n in z.namelist():
            if n.endswith((".xml", ".rels")): ET.fromstring(z.read(n))
        self.assertEqual(len(re.findall("<w:comment ", z.read("word/comments.xml").decode())), 2)
        self.assertIn("word/media/image1.png", z.namelist())
        self.assertEqual(png_size(z.read("word/media/image1.png")), (1, 1))

    def test_every_table_has_grid_matching_columns(self):
        doc = Doc(); doc.table([["A", "B", "C"], ["1", "2", "3"]]); doc.table([["X"]], header=False, widths=[9000])
        out = os.path.join(tempfile.mkdtemp(), "t.docx"); doc.save(out)
        xml = zipfile.ZipFile(out).read("word/document.xml").decode()
        grids = re.findall(r"<w:tblGrid>(.*?)</w:tblGrid>", xml)
        self.assertEqual([g.count("<w:gridCol") for g in grids], [3, 1])

    def test_non_png_rejected(self):
        p = os.path.join(tempfile.mkdtemp(), "x.png")
        with open(p, "wb") as fh:
            fh.write(b"nope")
        with self.assertRaises(ValueError): Doc().image(p)


class CorpusTests(unittest.TestCase):
    def test_update_vs_new_and_stale_text(self):
        from docaidev import corpus
        pages = corpus.load(os.path.join(EX, "published-docs"))
        tps = [{"title": "Viewing rack and cabinet equipment", "scope": "UPDATE"}, {"title": "Brand new topic", "scope": "NEW"}]
        r = Resolution(topic="Ports tab label", value="Ports", winner="live", confidence="NEEDS REVIEW", supporting=["live"], overruled={"tracker": "Interfaces"})
        out = corpus.scan(pages, "https://docs.example.com/x", tps, [r], "RACK-210")
        self.assertIn("PUBLISHED PAGE EXISTS", out["status"]["Viewing rack and cabinet equipment"])
        self.assertIn("NO PUBLISHED PAGE", out["status"]["Brand new topic"])
        self.assertEqual(out["mismatch"], [])
        self.assertEqual(len(out["changes"]), 1)                           # one row per stale sentence, not per phrase
        self.assertEqual(out["changes"][0][0], "viewing-rack-and-cabinet-equipment.md")   # file column intact
        self.assertIn("Open the Ports tab", out["changes"][0][3])           # stale phrase rewritten with the evidence value
        r2 = Resolution(topic="Cabling tab label", value="Cabling", winner="live", confidence="NEEDS REVIEW", supporting=["live"], overruled={"tracker": "Links"})
        both = corpus.scan(pages, "https://d", [], [r, r2], "S")["changes"]
        self.assertEqual(len(both), 1)
        self.assertIn("Open the Cabling tab", both[0][3]); self.assertIn("Open the Ports tab", both[0][3])   # both fixes in one row

    def test_scope_mismatch_flagged(self):
        from docaidev import corpus
        pages = corpus.load(os.path.join(EX, "published-docs"))
        out = corpus.scan(pages, "https://d", [{"title": "Viewing rack and cabinet equipment", "scope": "NEW"},
                                               {"title": "Not published", "scope": "UPDATE"}], [], "S")
        self.assertEqual(len(out["mismatch"]), 2)

    def test_blocks_and_topics_parsers(self):
        from docaidev.ac import blocks, topics
        with open(os.path.join(EX, "draft.md")) as fh:
            txt = fh.read()
        self.assertEqual([n for n, _ in blocks(txt, "Release notes")], ["Highlights", "New in this release", "UI changes"])
        self.assertEqual([t["scope"] for t in topics(txt)], ["UPDATE", "NEW", "NEW"])
        steps = dict(topics(txt)[2]["sections"])["Steps"]
        self.assertTrue(any(x.startswith("\u2192 Result") for x in steps))


class CommentCategoryTests(unittest.TestCase):
    def test_categories(self):
        R = lambda **k: Resolution(**{**dict(topic="t", value="v", winner="live", confidence="X", supporting=["live"]), **k})
        self.assertEqual(comment_for(R(overruled={"tracker": "old"}))[0], CORRECTION)
        self.assertEqual(comment_for(R(overruled={"repo": "old"}))[0], SME_NEEDED)
        self.assertEqual(comment_for(R(supporting=["live", "repo"]))[0], SOURCE_CONFIRMED)
        self.assertEqual(comment_for(R(winner="repo", supporting=["repo"]))[0], PM_DECISION)
        self.assertEqual(comment_for(R(winner="tracker", supporting=["tracker"]))[0], SME_NEEDED)


class CaptureTests(unittest.TestCase):
    def test_refuses_remote_host(self):
        with self.assertRaises(CaptureError): capture("http://example.com", recipe(), "T", tempfile.mkdtemp())

    @unittest.skipUnless(HAVE_PW, "playwright not installed")
    def test_seed_read_capture_cleanup(self):
        srv, url = start_app()
        try:
            res = capture(url, recipe(), "DOC_SEED_T", tempfile.mkdtemp(), log=lambda m: None)
            self.assertEqual((len(res.seeded), res.removed, res.leftovers, res.error), (8, 8, 0, ""))
            self.assertEqual(len(res.shots), 4)
            self.assertEqual([x["rows"] for x in res.shots], [3, 2, 2, 1])   # rack ports/cabling, cabinet ports/cabling
            live = {o["topic"]: o["value"] for o in res.observations}
            self.assertEqual(live["Ports tab label"], "Ports")
            self.assertEqual(live["Port columns"], "Device, Port, Speed, Status")
            self.assertEqual(live["Cable type options"], "Copper, Fibre, DAC")
            self.assertTrue(res.clean)
        finally:
            srv.shutdown(); srv.server_close()

    @unittest.skipUnless(HAVE_PW, "playwright not installed")
    def test_cleanup_runs_when_screenshot_fails(self):
        srv, url = start_app()
        try:
            r = recipe(timeout_ms=300)
            r["shots"] = [{"file": "x", "page": "/", "wait_selector": "#never"}]
            res = capture(url, r, "DOC_SEED_T", tempfile.mkdtemp(), log=lambda m: None)
            self.assertIn("screenshot failed", res.error)
            self.assertEqual((res.removed, res.leftovers), (8, 0))
        finally:
            srv.shutdown(); srv.server_close()


def ns(out, url, **kw):
    base = dict(key=os.path.join(EX, "spec.md"), tracker="paste", repo=[os.path.join(EX, "sample-repo")], ref=None, accuracy="1",
                observations=os.path.join(EX, "observations.json"), reviews=os.path.join(EX, "reviews-resolved.json"),
                precedence=None, exclude=None, out=None, confirm=["write " + out], docx=out, scope=None,
                app_url=url, seed=os.path.join(EX, "seed.json"), meta=os.path.join(EX, "meta.json"),
                draft=os.path.join(EX, "draft.md"), style=os.path.join(EX, "style.json"), docs=os.path.join(EX, "published-docs"), docs_url="https://docs.example.com/rack-manager")
    base.update(kw)
    return argparse.Namespace(**base)


class EndToEndDocxTests(unittest.TestCase):
    @unittest.skipUnless(HAVE_PW, "playwright not installed")
    def test_full_run_writes_word_doc(self):
        os.environ["DOC_AIDEV_HOME"] = tempfile.mkdtemp()
        srv, url = start_app()
        out = os.path.join(tempfile.mkdtemp(), "r.docx")
        try:
            self.assertEqual(run(ns(out, url), out=lambda m: None), 0)
        finally:
            srv.shutdown(); srv.server_close()
        z = zipfile.ZipFile(out)
        doc, com = z.read("word/document.xml").decode(), z.read("word/comments.xml").decode()
        self.assertEqual(len([n for n in z.namelist() if n.startswith("word/media/")]), 4)
        self.assertEqual(len(re.findall("<w:comment ", com)), len(re.findall("<w:commentReference", doc)))   # every comment is anchored
        for must in ("AUTHOR NOTES", "PM checklist", "SME checklist", "NO EVIDENCE found", "Instance verified", "Status on RackDemo",
                     "RELEASE NOTES \u2014 Highlights", "RELEASE NOTES \u2014 UI changes", "Section 2b \u2014 Release notes detail table",
                     "Ports tab on a rack", "Cabling tab on a cabinet", "Topic set derived from Phase 1 findings", "No reference topic",
                     "Behaviour notes", "Select the Ports tab.", "Select Edit connection on the connection you want to change.",
                     "CONCEPT", "UPDATE existing draft", "(NEW)", "LOCAL DRAFT EXISTS", "NO PUBLISHED PAGE", "SME-1", "SME-all", "PM-1", "[BLOCKER]",
                     "Screenshot evidence \u2014 populated tabs", "What this confirms", "Workspace", "DOC_SEED_RACK-210",
                     "Section 1 \u2014 Website / DITA scan findings (Phase 5b)", "Section 2 \u2014 Changes required", "DITA file", "Section/field"):
            self.assertIn(must, doc)
        self.assertIn("Open the Ports tab", doc)                       # the corrected published sentence appears in Section 2
        draft = doc.split("DRAFT TOPIC CONTENT")[1].split("AUTHOR NOTES")[0]
        prose = re.sub(r"\[(CORRECTION|SOURCE CONFIRMED|SME NEEDED)[^\]]*\]", "", draft)   # reviewer tags may quote the ticket; the text itself must not
        self.assertNotIn("Interfaces", prose); self.assertNotIn("Links", prose)
        self.assertNotIn("UNRESOLVED", doc)
        for cat in ("CORRECTION", "SOURCE CONFIRMED", "Style", "Structure", "Terminology", "Consistency", "Release notes", "Grammar",
                    "SME NEEDED", "PM DECISION NEEDED"):
            self.assertIn("[" + cat + "]", com)
        self.assertIn('w:author="Phase3-Generate"', com); self.assertIn('w:author="Phase4-Quality"', com)
        self.assertNotIn("Copper, Fibre', wording", com)               # no false positive on a fragment of the confirmed value

    def test_docx_not_written_without_confirmation(self):
        os.environ["DOC_AIDEV_HOME"] = tempfile.mkdtemp()
        out = os.path.join(tempfile.mkdtemp(), "r.docx")
        self.assertEqual(run(ns(out, None, confirm=["yes"], app_url=None, seed=None, reviews=None), out=lambda m: None), 4)
        self.assertFalse(os.path.exists(out))

    def test_docx_without_environment_still_builds_and_flags_gap(self):
        os.environ["DOC_AIDEV_HOME"] = tempfile.mkdtemp()
        out = os.path.join(tempfile.mkdtemp(), "r.docx")
        self.assertEqual(run(ns(out, None, app_url=None, seed=None), out=lambda m: None), 0)
        xml = zipfile.ZipFile(out).read("word/document.xml").decode()
        self.assertIn("not checked", xml)                      # metadata says the environment was not verified
        self.assertNotIn("word/media/", " ".join(zipfile.ZipFile(out).namelist()))  # and no screenshots exist


if __name__ == "__main__":
    unittest.main()
