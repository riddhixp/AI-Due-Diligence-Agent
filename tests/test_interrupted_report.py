import unittest
from interrupted_report import interrupted_report


class InterruptedReportTests(unittest.TestCase):
    def test_unreviewed_submission_not_claimed_verified(self):
        text = interrupted_report(
            {"revenue_current": 130}, 0, 1, None)
        self.assertIn("Latest submission reviewed: No", text)
        self.assertIn("Unavailable or stale", text)
        self.assertIn("not** a completed", text)

    def test_reviewed_failure_remains_visible(self):
        text = interrupted_report(
            {"revenue_current": 130}, 1, 1, "NEEDS_REVIEW")
        self.assertIn("NEEDS_REVIEW", text)

    def test_empty_run_does_not_fabricate_data(self):
        text = interrupted_report({}, 0, 0, None)
        self.assertIn("Accepted financial submissions: 0", text)
        self.assertNotIn("Submitted FY revenue", text)


if __name__ == "__main__":
    unittest.main()
