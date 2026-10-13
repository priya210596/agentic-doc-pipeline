import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from docaidev.ac import extract_acceptance_criteria
from docaidev.adapters import get_adapter, AdapterError
from docaidev.adapters.jira import _adf_to_text


class T(unittest.TestCase):
    def test_ac_markdown_heading(self):
        txt = "Intro\n\n## Acceptance criteria\n- [ ] User can log in\n- [x] Error shown on bad password\n\n## Notes\n- not this\n"
        self.assertEqual(extract_acceptance_criteria(txt), ["User can log in", "Error shown on bad password"])

    def test_ac_numbered_bold_heading(self):
        txt = "**Acceptance Criteria:**\n1. First\n2) Second\n"
        self.assertEqual(extract_acceptance_criteria(txt), ["First", "Second"])

    def test_ac_none(self):
        self.assertEqual(extract_acceptance_criteria("just a description"), [])
        self.assertEqual(extract_acceptance_criteria(""), [])

    def test_paste_adapter_and_coverage(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("# Export report\n\n## Acceptance criteria\n- Exports CSV\n")
        item = get_adapter("paste").fetch(f.name)
        self.assertEqual(item.title, "Export report")
        cov = item.coverage()
        self.assertTrue(cov["acceptance_criteria"]["found"])
        self.assertFalse(cov["linked_changes"]["found"])

    def test_unknown_tracker(self):
        with self.assertRaises(AdapterError):
            get_adapter("nope")

    def test_adf(self):
        adf = {"type": "doc", "content": [{"type": "bulletList", "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "A"}]}]}]}]}
        self.assertEqual(_adf_to_text(adf).strip(), "- A")


if __name__ == "__main__":
    unittest.main()
