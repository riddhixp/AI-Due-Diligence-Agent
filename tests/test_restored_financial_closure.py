import unittest
from investigation_checkpoint import create_checkpoint, document_fingerprint
from tool_state_rebinding import prepare_tool_state
from investigation_control import submission_block_reason


class RestoredFinancialClosureTests(unittest.TestCase):
    def test_two_submissions_remain_exhausted(self):
        pdf = b"fixture"
        checkpoint = create_checkpoint(
            document_fingerprint(pdf), {"revenue_current": 120},
            2, 2, "PRELIMINARY_CHECKS_PASSED",
            ["submit_financial_data", "review_submitted_financials",
             "read_page", "submit_financial_data", "review_submitted_financials"],
        )
        prepared = prepare_tool_state(checkpoint, pdf)
        reason = submission_block_reason(
            prepared["submission_attempts"]["count"],
            prepared["review_state"]["reviewed_count"],
            prepared["review_state"]["status"], 0,
        )
        self.assertIn("SUBMISSION_LIMIT_REACHED", reason)

    def test_unreviewed_submission_stays_blocked(self):
        pdf = b"fixture"
        checkpoint = create_checkpoint(
            document_fingerprint(pdf), {"revenue_current": 130},
            1, 0, None, ["read_page", "submit_financial_data"],
        )
        prepared = prepare_tool_state(checkpoint, pdf)
        review = prepared["review_state"]
        reason = submission_block_reason(
            prepared["submission_attempts"]["count"],
            review["reviewed_count"], review["status"],
            review["page_reads"] - review["reads_at_review"],
        )
        self.assertIn("REVIEW_REQUIRED", reason)


if __name__ == "__main__":
    unittest.main()
