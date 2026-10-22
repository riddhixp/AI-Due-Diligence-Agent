import unittest

from report_verification import finalise_dd_report


class ReportVerificationTests(unittest.TestCase):
    def test_missing_submission_prefaces_report_with_warning(self):
        report = finalise_dd_report("# Findings", {}, None)
        self.assertIn("Financial evidence not fully verified", report)
        self.assertTrue(report.endswith("# Findings"))

    def test_unresolved_source_warning_survives_export(self):
        report = finalise_dd_report(
            "# Findings", {"company": "Demo"},
            {"status": "NEEDS_REVIEW", "metadata_issues": ["units missing"]},
        )
        self.assertIn("units missing", report)
        self.assertIn("human validation", report)

    def test_preliminary_pass_is_not_labelled_audit(self):
        report = finalise_dd_report(
            "# Findings", {"company": "Demo"},
            {"status": "PRELIMINARY_CHECKS_PASSED"},
        )
        self.assertIn("Preliminary checks passed", report)
        self.assertIn("not a full financial audit", report)

    def test_idempotent_formatting(self):
        first = finalise_dd_report("# Findings", {}, None)
        second = finalise_dd_report(first, {}, None)
        self.assertEqual(first, second)

    def test_none_report_is_handled(self):
        report = finalise_dd_report(None, {}, None)
        self.assertIn("Evidence verification status", report)


if __name__ == "__main__":
    unittest.main()
