import unittest

from tool_sequence_audit import assess_tool_sequence


class ToolSequenceAuditTests(unittest.TestCase):
    def test_initial_submission_and_review(self):
        self.assertTrue(assess_tool_sequence([
            "read_page", "submit_financial_data", "review_submitted_financials"
        ])["sequence_ok"])

    def test_evidence_supported_correction_order(self):
        self.assertTrue(assess_tool_sequence([
            "submit_financial_data", "review_submitted_financials",
            "read_page", "submit_financial_data", "review_submitted_financials"
        ])["sequence_ok"])

    def test_missing_review(self):
        result = assess_tool_sequence(["submit_financial_data"])
        self.assertIn("NO_REVIEW_TOOL_CALL", result["issues"])

    def test_unreviewed_second_submission(self):
        result = assess_tool_sequence([
            "submit_financial_data", "review_submitted_financials",
            "read_page", "submit_financial_data",
        ])
        self.assertIn("CORRECTION_NOT_FOLLOWED_BY_REVIEW", result["issues"])

    def test_read_page_before_failed_review_does_not_count(self):
        result = assess_tool_sequence([
            "read_page", "submit_financial_data",
            "review_submitted_financials", "submit_financial_data",
            "review_submitted_financials",
        ])
        self.assertIn("NO_PAGE_READ_AFTER_REVIEW", result["issues"])

    def test_correction_without_intervening_review(self):
        result = assess_tool_sequence([
            "submit_financial_data", "read_page", "submit_financial_data",
            "review_submitted_financials",
        ])
        self.assertIn("CORRECTION_WITHOUT_INTERVENING_REVIEW", result["issues"])

    def test_three_submissions_flagged(self):
        result = assess_tool_sequence([
            "submit_financial_data", "review_submitted_financials",
            "read_page", "submit_financial_data", "review_submitted_financials",
            "submit_financial_data", "review_submitted_financials",
        ])
        self.assertIn("EXCESS_SUBMISSION_TOOL_CALLS", result["issues"])


if __name__ == "__main__":
    unittest.main()
