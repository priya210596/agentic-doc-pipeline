import os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from docaidev.repo import RepoAdapter, RepoError, is_test_path
from docaidev.reconcile import ConsistencyThread, Finding, Reconciler, CONFIRMED, NEEDS_REVIEW, ASSUMED
from docaidev.gates import accuracy_gate, unresolved_threads, ReviewThread, WriteConfirmation
from docaidev.output import render_markdown


def write(path, text):
    with open(path, "w") as fh:
        fh.write(text)


def make_repo():
    d = tempfile.mkdtemp()
    run = lambda *a: subprocess.run(["git", "-C", d] + list(a), check=True, capture_output=True)
    run("init", "-q", "-b", "main")
    run("config", "user.email", "t@example.com"); run("config", "user.name", "t")
    os.makedirs(os.path.join(d, "src")); os.makedirs(os.path.join(d, "tests"))
    write(os.path.join(d, "src/a.py"), "# FEAT-1 export\n")
    write(os.path.join(d, "tests/test_a.py"), "# covers FEAT-1\n")
    run("add", "-A"); run("commit", "-q", "-m", "base")
    run("checkout", "-q", "-b", "feature")
    write(os.path.join(d, "src/b.py"), "x = 1\n")
    run("add", "-A"); run("commit", "-q", "-m", "feat")
    return d


class RepoTests(unittest.TestCase):
    def setUp(self):
        self.d = make_repo(); self.r = RepoAdapter([self.d])

    def test_check(self):
        self.assertTrue(self.r.check()[0][1])
        self.assertFalse(RepoAdapter(["/nope/x"]).check()[0][1])

    def test_changed_files(self):
        self.assertEqual(self.r.changed_files(self.d, "main", "feature"), ["src/b.py"])

    def test_references_and_tests(self):
        self.assertEqual(sorted(self.r.references("FEAT-1")[self.r.paths[0]]), ["src/a.py", "tests/test_a.py"])
        self.assertEqual(list(self.r.tests_for("FEAT-1").values())[0], ["tests/test_a.py"])

    def test_read_blocks_traversal_and_unlisted_repo(self):
        with self.assertRaises(RepoError): self.r.read(self.d, "../../etc/passwd")
        with self.assertRaises(RepoError): self.r.read("/tmp", "x")
        self.assertIn("FEAT-1", self.r.read(self.d, "src/a.py"))

    def test_is_test_path(self):
        self.assertTrue(is_test_path("tests/x.py")); self.assertTrue(is_test_path("web/login.spec.ts"))
        self.assertFalse(is_test_path("src/latest.py"))


class ReconcileTests(unittest.TestCase):
    ORDER = ["live", "walkthrough", "repo", "tracker"]

    def test_conflict_flagged_immediately(self):
        t = ConsistencyThread()
        self.assertEqual(t.add(Finding("Save button", "Save", "tracker")), [])
        clash = t.add(Finding("Save button", "Submit", "live"))
        self.assertEqual(len(clash), 1)
        self.assertEqual(list(t.conflicts()), ["Save button"])

    def test_whitespace_and_case_not_a_conflict(self):
        t = ConsistencyThread(); t.add(Finding("x", "Export  CSV", "repo"))
        self.assertEqual(t.add(Finding("x", "export csv", "tracker")), [])

    def test_precedence_wins_and_is_auditable(self):
        fs = [Finding("label", "Save", "tracker"), Finding("label", "Submit", "live")]
        r = Reconciler(self.ORDER).resolve(fs)[0]
        self.assertEqual((r.value, r.winner, r.confidence), ("Submit", "live", NEEDS_REVIEW))
        self.assertEqual(r.overruled, {"tracker": "Save"})

    def test_agreement_confirmed(self):
        fs = [Finding("l", "A", "repo"), Finding("l", "A", "tracker")]
        self.assertEqual(Reconciler(self.ORDER).resolve(fs)[0].confidence, CONFIRMED)

    def test_single_source_confidence_depends_on_rank(self):
        rec = Reconciler(self.ORDER)
        self.assertEqual(rec.resolve([Finding("a", "1", "live")])[0].confidence, CONFIRMED)
        self.assertEqual(rec.resolve([Finding("a", "1", "tracker")])[0].confidence, NEEDS_REVIEW)

    def test_excluded_source_ignored_or_assumed(self):
        rec = Reconciler(self.ORDER, excluded=["tracker"])
        both = rec.resolve([Finding("a", "old", "tracker"), Finding("a", "new", "repo")])[0]
        self.assertEqual((both.value, both.winner), ("new", "repo"))
        only = rec.resolve([Finding("b", "old", "tracker")])[0]
        self.assertEqual(only.confidence, ASSUMED)

    def test_unranked_source_is_least_trusted(self):
        r = Reconciler(self.ORDER).resolve([Finding("a", "x", "rumour"), Finding("a", "y", "tracker")])[0]
        self.assertEqual(r.winner, "tracker")

    def test_duplicate_precedence_rejected(self):
        with self.assertRaises(ValueError): Reconciler(["a", "a"])


class GateTests(unittest.TestCase):
    def test_accuracy_gate(self):
        self.assertTrue(accuracy_gate("1").proceed)
        g = accuracy_gate("incomplete", missing_fields=["acceptance_criteria"])
        self.assertEqual(g.flags, ["UNCONFIRMED:acceptance_criteria"])
        self.assertEqual(accuracy_gate("3", "jira").excluded_sources, ["jira"])
        self.assertFalse(accuracy_gate("4").proceed)
        with self.assertRaises(ValueError): accuracy_gate("7")

    def test_no_silent_skip(self):
        ts = [ReviewThread("1", "c", "changed"), ReviewThread("2", "c"),
              ReviewThread("3", "c", "ignored"), ReviewThread("4", "c", "ignored", "out of scope")]
        bad = {t.id: why for t, why in unresolved_threads(ts)}
        self.assertEqual(bad, {"2": "no disposition", "3": "ignored without a reason"})

    def test_write_confirmation_is_per_target(self):
        w = WriteConfirmation()
        self.assertFalse(w.confirm("a.md", "yes"))
        self.assertTrue(w.confirm("a.md", "Write a.md"))
        self.assertTrue(w.allowed("a.md")); self.assertFalse(w.allowed("b.md"))


class OutputTests(unittest.TestCase):
    def test_every_claim_tagged(self):
        res = Reconciler(["live", "tracker"]).resolve([Finding("label", "Save", "tracker"), Finding("label", "Submit", "live")])
        md = render_markdown("Doc", res, [ReviewThread("1", "fix typo", "changed")])
        self.assertIn("[NEEDS REVIEW] **label:** Submit", md)
        self.assertIn("tracker said \"Save\"", md)
        self.assertIn("1: fix typo -> changed", md)


if __name__ == "__main__":
    unittest.main()
