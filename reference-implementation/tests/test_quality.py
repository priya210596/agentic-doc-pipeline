import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from docaidev import quality as q

STYLE = {"spelling": {"customise": "customize"}, "banned_step_openers": ["Navigate to"], "max_rn_sentence_words": 10,
         "serial_comma": True, "heading_case": "sentence"}


def cats(comments):
    return [c.split("]")[0].lstrip("[") for c in comments]


class QualityTests(unittest.TestCase):
    def test_spelling(self):
        self.assertEqual(cats(q.check_line("You can customise it.", "body", STYLE)), ["Style"])
        self.assertEqual(q.check_line("You can customize it.", "body", STYLE), [])

    def test_banned_step_opener_only_in_steps(self):
        self.assertEqual(cats(q.check_line("Navigate to Settings.", "step", STYLE)), ["Style"])
        self.assertEqual(q.check_line("Navigate to Settings.", "body", STYLE), [])

    def test_rn_sentence_length(self):
        long = "This sentence has far more than ten words in it so it should be flagged."
        self.assertEqual(cats(q.check_line(long, "rn", STYLE)), ["Release notes"])
        self.assertEqual(q.check_line(long, "body", STYLE), [])

    def test_serial_comma(self):
        self.assertEqual(cats(q.check_line("Check the device, port and speed.", "body", STYLE)), ["Grammar"])
        self.assertEqual(q.check_line("Check the device, port, and speed.", "body", STYLE), [])

    def test_exact_case_label_needs_suffix_context(self):
        labels = [("Ports", " tab")]
        self.assertEqual(cats(q.check_line("Open the ports tab.", "body", STYLE, labels)), ["Terminology"])
        self.assertEqual(q.check_line("Open the Ports tab.", "body", STYLE, labels), [])
        self.assertEqual(q.check_line("Many ports are free.", "body", STYLE, labels), [])      # plain word, not the label

    def test_consistency_with_overruled_wording_and_prefix_false_positive(self):
        self.assertEqual(cats(q.check_line("Shows interfaces.", "body", STYLE, overruled=["Interfaces"])), ["Consistency"])
        # 'Copper, Fibre' is only a fragment of the confirmed 'Copper, Fibre, DAC': not a conflict
        self.assertEqual(q.check_line("Choose: Copper, Fibre, DAC.", "body", STYLE, overruled=["Copper, Fibre"],
                                      confirmed=["Copper, Fibre, DAC"]), [])

    def test_sme_and_pm_flags(self):
        self.assertEqual(cats(q.check_line("[SME NEEDED] Confirm the role.", "body", STYLE)), ["SME NEEDED"])
        self.assertEqual(cats(q.check_line("The Utilisation column is optional.", "body", {}, pm_topics=["Utilisation column"])), ["PM DECISION NEEDED"])

    def test_heading_case(self):
        self.assertEqual(cats(q.check_heading("Key Benefits", STYLE)), ["Structure"])
        self.assertEqual(q.check_heading("Key benefits", STYLE), [])
        self.assertEqual(q.check_heading("Key Benefits", {}), [])        # rule off without config

    def test_no_style_guide_means_no_findings(self):
        self.assertEqual(q.check_line("You can customise it, Navigate to x.", "step", {}), [])


if __name__ == "__main__":
    unittest.main()
