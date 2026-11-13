"""Reviews may repeat, but cannot establish a review before submission."""
import unittest
from investigation_checkpoint import create_checkpoint, document_fingerprint
from tool_state_rebinding import prepare_tool_state


class ReviewCheckpointReplayTests(unittest.TestCase):
    def checkpoint(self, events, reviewed=1, submissions=1):
        return create_checkpoint(document_fingerprint(b'pdf'), {'revenue_current': 130},
                                 submissions, reviewed, 'NEEDS_REVIEW', events)

    def test_repeated_review_does_not_inflate_reviewed_submission_count(self):
        state = prepare_tool_state(self.checkpoint([
            'submit_financial_data', 'review_submitted_financials', 'read_page',
            'review_submitted_financials', 'read_page']), b'pdf')
        review = state['review_state']
        self.assertEqual(review['reviewed_count'], 1)
        self.assertEqual(review['page_reads'], 2)
        self.assertEqual(review['reads_at_review'], 1)

    def test_reordering_review_before_submission_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'REVIEW_BEFORE_SUBMISSION'):
            prepare_tool_state(self.checkpoint([
                'review_submitted_financials', 'submit_financial_data']), b'pdf')

    def test_repeated_first_review_cannot_claim_second_submission_reviewed(self):
        with self.assertRaisesRegex(ValueError, 'REVIEW_TRACE_COUNT_MISMATCH'):
            prepare_tool_state(self.checkpoint([
                'submit_financial_data', 'review_submitted_financials',
                'review_submitted_financials', 'read_page', 'submit_financial_data'],
                reviewed=2, submissions=2), b'pdf')
