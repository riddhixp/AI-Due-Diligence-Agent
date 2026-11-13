import unittest

from investigation_outcome import investigation_outcome


class InvestigationOutcomeTests(unittest.TestCase):
    def test_no_submission(self):
        result = investigation_outcome(0, 0, None, [])
        self.assertEqual(result["outcome"], "NO_FINANCIAL_SUBMISSION")

    def test_unreviewed_submission_not_treated_as_pass(self):
        result = investigation_outcome(1, 0, None, ["submit_financial_data"])
        self.assertEqual(result["outcome"], "LATEST_SUBMISSION_UNREVIEWED")
        self.assertFalse(result["latest_submission_reviewed"])

    def test_latest_correction_needs_fresh_review(self):
        result = investigation_outcome(
            2, 1, "NEEDS_REVIEW", ["submit_financial_data"] * 2
        )
        self.assertEqual(result["outcome"], "LATEST_SUBMISSION_UNREVIEWED")

    def test_initial_review_unresolved(self):
        result = investigation_outcome(
            1, 1, "NEEDS_REVIEW", ["review_submitted_financials"]
        )
        self.assertEqual(result["outcome"], "INITIAL_SUBMISSION_NEEDS_REVIEW")

    def test_correction_is_not_success_when_still_flagged(self):
        result = investigation_outcome(
            2, 2, "NEEDS_REVIEW", ["read_page", "review_submitted_financials"] * 2
        )
        self.assertEqual(result["outcome"], "CORRECTION_STILL_NEEDS_REVIEW")
        self.assertEqual(result["page_reads"], 2)

    def test_correction_success_is_only_preliminary(self):
        result = investigation_outcome(
            2, 2, "PRELIMINARY_CHECKS_PASSED",
            ["submit_financial_data", "read_page",
             "submit_financial_data", "review_submitted_financials"],
        )
        self.assertEqual(result["outcome"], "CORRECTION_PASSED_PRELIMINARY_CHECKS")
        self.assertTrue(result["correction_attempted"])

    def test_initial_success(self):
        result = investigation_outcome(
            1, 1, "PRELIMINARY_CHECKS_PASSED", ["review_submitted_financials"]
        )
        self.assertEqual(result["outcome"], "INITIAL_SUBMISSION_PASSED_PRELIMINARY_CHECKS")


if __name__ == "__main__":
    unittest.main()
