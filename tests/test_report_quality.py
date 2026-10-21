
import unittest

from report_quality import check_report_quality, REQUIRED_SECTIONS


class TestReportQuality(unittest.TestCase):

    def test_empty_report(self):
        issues = check_report_quality("")
        self.assertIn("The report is empty.", issues)

    def test_missing_sections(self):
        issues = check_report_quality(
            "# Executive assessment\nRevenue increased."
        )

        self.assertTrue(
            any("Missing section:" in issue for issue in issues)
        )

    def test_mechanical_labels(self):
        report = "\n".join(
            f"# {section}" for section in REQUIRED_SECTIONS
        )

        report += "\n1. Finding - Revenue increased."

        issues = check_report_quality(report)

        self.assertIn(
            "Mechanical labels detected in the report.",
            issues,
        )

    def test_clean_report(self):
        report = "\n\n".join(
            f"# {section}\n"
            "The financial evidence supports a preliminary "
            "assessment, subject to further verification."
            for section in REQUIRED_SECTIONS
        )

        issues = check_report_quality(report)

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
