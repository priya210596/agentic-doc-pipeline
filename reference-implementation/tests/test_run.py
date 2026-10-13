import os, sys, tempfile, unittest, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from docaidev import config
from docaidev.run import run

E = os.path.join(os.path.dirname(__file__), "..", "examples", "rack-manager")


def args(**kw):
    base = dict(key=os.path.join(E, "spec.md"), tracker="paste", repo=[os.path.join(E, "sample-repo")], ref="RACK-210",
                accuracy="1", observations=os.path.join(E, "observations.json"), reviews=None,
                precedence=None, exclude=None, out=None, confirm=None)
    base.update(kw)
    return argparse.Namespace(**base)


class RunTests(unittest.TestCase):
    def setUp(self):
        os.environ["DOC_AIDEV_HOME"] = tempfile.mkdtemp()

    def go(self, **kw):
        lines = []
        code = run(args(**kw), out=lines.append)
        return code, "\n".join(lines)

    def test_conflicts_found_and_resolved_by_precedence(self):
        code, text = self.go()
        self.assertEqual(code, 0)
        self.assertIn("CONFLICT on 'Ports tab label'", text)
        draft = text.split("== 8. Draft ==")[1]
        self.assertIn("[NEEDS REVIEW] **Ports tab label:** Ports", draft)      # walkthrough beats the ticket's "Interfaces"
        self.assertIn("tracker said \"Interfaces\"", draft)
        self.assertIn("[NEEDS REVIEW] **Cable type options:** Copper, Fibre, DAC", draft)  # code beats the ticket (no live check in this test)

    def test_inaccurate_tracker_is_excluded(self):
        code, text = self.go(accuracy="3")
        self.assertIn("excluded: tracker", text)
        self.assertNotIn("Interfaces", text.split("== 8. Draft ==")[1])

    def test_pause_stops_everything(self):
        code, text = self.go(accuracy="4")
        self.assertEqual(code, 2); self.assertNotIn("Repo scan", text)

    def test_unresolved_review_blocks(self):
        code, text = self.go(reviews=os.path.join(E, "reviews-blocked.json"))
        self.assertEqual(code, 3)
        self.assertIn("BLOCKED thread R2: no disposition", text)
        self.assertIn("BLOCKED thread R3: ignored without a reason", text)

    def test_write_requires_exact_confirmation(self):
        out = os.path.join(tempfile.mkdtemp(), "d.md")
        code, _ = self.go(reviews=os.path.join(E, "reviews-resolved.json"), out=out, confirm="yes")
        self.assertEqual(code, 4); self.assertFalse(os.path.exists(out))
        code, _ = self.go(reviews=os.path.join(E, "reviews-resolved.json"), out=out, confirm="write " + out)
        self.assertEqual(code, 0)
        with open(out) as fh:
            self.assertIn("Ports tab label", fh.read())

    def test_missing_repo_fails_cleanly(self):
        code, text = self.go(repo=["/nope/missing"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
