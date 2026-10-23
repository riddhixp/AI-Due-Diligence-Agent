import unittest
from investigation_checkpoint import create_checkpoint, document_fingerprint
from financial_state_restore import restore_financial_state


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"synthetic pdf"
        self.checkpoint = create_checkpoint(
            document_fingerprint(self.pdf),
            {"revenue_current": 130}, 1, 0, None,
            ["submit_financial_data"],
        )

    def test_valid_unreviewed_state_preserved(self):
        restored = restore_financial_state(self.checkpoint, self.pdf)
        self.assertEqual(restored["financial_submission"]["revenue_current"], 130)
        self.assertEqual(restored["submission_count"], 1)
        self.assertFalse(restored["conversation_restored"])

    def test_other_pdf_rejected(self):
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            restore_financial_state(self.checkpoint, b"different pdf")

    def test_invalid_counters_rejected(self):
        self.checkpoint["reviewed_count"] = 2
        with self.assertRaisesRegex(ValueError, "INVALID_SUBMISSION_COUNTERS"):
            restore_financial_state(self.checkpoint, self.pdf)

    def test_stale_review_status_rejected(self):
        self.checkpoint["review_status"] = "PRELIMINARY_CHECKS_PASSED"
        with self.assertRaisesRegex(ValueError, "STALE_REVIEW_STATUS"):
            restore_financial_state(self.checkpoint, self.pdf)

    def test_restoration_does_not_mutate_checkpoint(self):
        result = restore_financial_state(self.checkpoint, self.pdf)
        result["financial_submission"]["revenue_current"] = 120
        self.assertEqual(self.checkpoint["financial_data"]["revenue_current"], 130)

    def test_corrected_submission_can_wait_for_its_own_review(self):
        from tool_state_rebinding import prepare_tool_state
        checkpoint = create_checkpoint(document_fingerprint(self.pdf),
            {'revenue_current': 120}, 2, 1, None,
            ['submit_financial_data', 'review_submitted_financials',
             'read_page', 'submit_financial_data'])
        restored = prepare_tool_state(checkpoint, self.pdf)
        self.assertEqual(restored['submission_attempts']['count'], 2)
        self.assertEqual(restored['review_state']['reviewed_count'], 1)
        self.assertIsNone(restored['review_state']['status'])
        self.assertEqual(restored['financial_submission']['revenue_current'], 120)

    def test_latest_review_still_requires_a_status(self):
        self.checkpoint['reviewed_count'] = 1
        self.checkpoint['tool_calls'].append('review_submitted_financials')
        with self.assertRaisesRegex(ValueError, 'MISSING_REVIEW_STATUS'):
            restore_financial_state(self.checkpoint, self.pdf)

    def test_earlier_status_cannot_validate_unreviewed_correction(self):
        from tool_state_rebinding import prepare_tool_state
        checkpoint = create_checkpoint(document_fingerprint(self.pdf),
            {'revenue_current': 120}, 2, 1, 'PRELIMINARY_CHECKS_PASSED',
            ['submit_financial_data', 'review_submitted_financials',
             'read_page', 'submit_financial_data'])
        with self.assertRaisesRegex(ValueError, 'STALE_LATEST_REVIEW'):
            prepare_tool_state(checkpoint, self.pdf)


if __name__ == "__main__":
    unittest.main()
