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


class SourceRecoveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.observed = ['read_page', 'submit_financial_data', 'review_submitted_financials',
                         'read_page', 'source_recheck_refused', 'read_page',
                         'submit_financial_data', 'review_submitted_financials']
        self.attempted = ['submit_financial_data' if event == 'source_recheck_refused' else event
                          for event in self.observed]

    def test_recorded_source_refusal_allows_valid_recovery(self):
        result = assess_tool_sequence(self.attempted, observed_tool_calls=self.observed)
        self.assertTrue(result['sequence_ok'])
        self.assertEqual(result['submissions_called'], 2)
        self.assertEqual(result['submission_attempts'], 3)
        self.assertEqual(result['source_recheck_refusals'], 1)

    def test_unaccounted_attempts_remain_blocked(self):
        result = assess_tool_sequence(self.attempted + ['submit_financial_data'],
                                      observed_tool_calls=self.observed)
        self.assertFalse(result['sequence_ok'])
        self.assertIn('UNACCOUNTED_SUBMISSION_TOOL_CALLS', result['issues'])

    def test_recovery_still_requires_latest_review(self):
        result = assess_tool_sequence(self.attempted[:-1], observed_tool_calls=self.observed[:-1])
        self.assertFalse(result['sequence_ok'])
        self.assertIn('CORRECTION_NOT_FOLLOWED_BY_REVIEW', result['issues'])

    def test_third_accepted_submission_is_still_excessive(self):
        extra = ['submit_financial_data', 'review_submitted_financials']
        result = assess_tool_sequence(self.attempted + extra, observed_tool_calls=self.observed + extra)
        self.assertFalse(result['sequence_ok'])
        self.assertIn('EXCESS_SUBMISSION_TOOL_CALLS', result['issues'])

    def test_missing_sdk_review_cannot_use_recorded_review(self):
        result = assess_tool_sequence(self.attempted[:-1], observed_tool_calls=self.observed)
        self.assertFalse(result['sequence_ok'])
        self.assertIn('TOOL_TRACE_MISMATCH', result['issues'])

    def test_reordered_sdk_calls_cannot_pass_on_matching_counts(self):
        altered = self.attempted.copy()
        altered[2], altered[3] = altered[3], altered[2]
        result = assess_tool_sequence(altered, observed_tool_calls=self.observed)
        self.assertFalse(result['sequence_ok'])
        self.assertIn('TOOL_TRACE_MISMATCH', result['issues'])

    def test_missing_sdk_source_read_is_detected(self):
        result = assess_tool_sequence(self.attempted[1:], observed_tool_calls=self.observed)
        self.assertFalse(result['sequence_ok'])
        self.assertIn('TOOL_TRACE_MISMATCH', result['issues'])

    def test_search_and_calculator_calls_do_not_change_financial_trace(self):
        result = assess_tool_sequence(['search_report', 'calculator'] + self.attempted,
                                      observed_tool_calls=self.observed)
        self.assertTrue(result['sequence_ok'])
