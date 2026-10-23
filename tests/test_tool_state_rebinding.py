import unittest
from investigation_checkpoint import create_checkpoint, document_fingerprint
from tool_state_rebinding import prepare_tool_state
from investigation_control import submission_block_reason


class ToolStateRebindingTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"test fixture"
        self.checkpoint = create_checkpoint(
            document_fingerprint(self.pdf), {"revenue_current": 130},
            1, 1, "NEEDS_REVIEW",
            ["read_page", "submit_financial_data", "review_submitted_financials"],
        )

    def test_counters_and_review_survive(self):
        result = prepare_tool_state(self.checkpoint, self.pdf)
        self.assertEqual(result["submission_attempts"]["count"], 1)
        self.assertEqual(result["review_state"]["reviewed_count"], 1)
        self.assertEqual(result["review_state"]["status"], "NEEDS_REVIEW")
        self.assertFalse(result["model_conversation_restored"])

    def test_page_read_before_review_does_not_authorize_correction(self):
        result = prepare_tool_state(self.checkpoint, self.pdf)
        review = result["review_state"]
        reason = submission_block_reason(
            1, review["reviewed_count"], review["status"],
            review["page_reads"] - review["reads_at_review"],
        )
        self.assertIn("SOURCE_RECHECK_REQUIRED", reason)

    def test_recheck_after_review_is_counted(self):
        self.checkpoint["tool_calls"].append("read_page")
        review = prepare_tool_state(self.checkpoint, self.pdf)["review_state"]
        self.assertEqual(review["page_reads"] - review["reads_at_review"], 1)

    def test_submission_counter_cannot_disagree_with_trace(self):
        self.checkpoint["tool_calls"] = ["read_page", "review_submitted_financials"]
        with self.assertRaisesRegex(ValueError, "SUBMISSION_TRACE_COUNT_MISMATCH"):
            prepare_tool_state(self.checkpoint, self.pdf)

    def test_review_counter_cannot_disagree_with_trace(self):
        self.checkpoint["tool_calls"] = ["submit_financial_data"]
        with self.assertRaisesRegex(ValueError, "REVIEW_TRACE_COUNT_MISMATCH"):
            prepare_tool_state(self.checkpoint, self.pdf)

    def test_mismatched_pdf_rejected(self):
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            prepare_tool_state(self.checkpoint, b"other pdf")

    def test_restoration_copies_nested_state(self):
        restored = prepare_tool_state(self.checkpoint, self.pdf)
        restored["financial_submission"]["revenue_current"] = 120
        self.assertEqual(self.checkpoint["financial_data"]["revenue_current"], 130)


if __name__ == "__main__":
    unittest.main()


class SourcePageHistoryTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b'fixture'
        self.checkpoint = create_checkpoint(document_fingerprint(self.pdf),
            {'revenue_current': 130}, 1, 1, 'NEEDS_REVIEW',
            ['read_page', 'submit_financial_data', 'review_submitted_financials', 'read_page'],
            page_read_events=[{'tool_index': 0, 'page': 2}, {'tool_index': 3, 'page': 1}])

    def test_only_page_read_after_review_authorizes_source_recheck(self):
        restored = prepare_tool_state(self.checkpoint, self.pdf)
        self.assertEqual(restored['review_state']['source_pages_since_review'], {1})
        restored['page_read_events'][0]['page'] = 99
        self.assertEqual(self.checkpoint['page_read_events'][0]['page'], 2)

    def test_legacy_checkpoint_does_not_invent_source_page_history(self):
        self.checkpoint.pop('page_read_events')
        restored = prepare_tool_state(self.checkpoint, self.pdf)
        self.assertEqual(restored['review_state']['source_pages_since_review'], set())
        self.assertEqual(restored['review_state']['page_reads'], 2)

    def test_invalid_history_is_rejected(self):
        for history in [None, {}, [{'tool_index': 1, 'page': 2}],
                        [{'tool_index': True, 'page': 2}], [{'tool_index': 0, 'page': True}],
                        [{'tool_index': 0, 'page': 0}], [{'tool_index': 9, 'page': 2}],
                        [{'tool_index': 3, 'page': 1}, {'tool_index': 0, 'page': 2}],
                        [{'tool_index': 0, 'page': 2}, {'tool_index': 0, 'page': 1}]]:
            with self.subTest(history=history):
                self.checkpoint['page_read_events'] = history
                with self.assertRaisesRegex(ValueError, 'INVALID_PAGE_READ_HISTORY'):
                    prepare_tool_state(self.checkpoint, self.pdf)
