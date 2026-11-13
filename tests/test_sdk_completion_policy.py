import unittest
from sdk_completion_policy import sdk_continuation_complete


class SDKCompletionPolicyTests(unittest.TestCase):
    def test_fresh_report_not_blocked_by_missing_handoff(self):
        self.assertTrue(sdk_continuation_complete({"evaluation": "PRELIMINARY_PASS"}))

    def test_approved_does_not_equal_completed(self):
        self.assertFalse(sdk_continuation_complete(
            {"evaluation": "PRELIMINARY_PASS"}, {"status": "APPROVED"}
        ))

    def test_rejected_does_not_equal_completed(self):
        self.assertFalse(sdk_continuation_complete(
            {"evaluation": "PRELIMINARY_PASS"}, {"status": "REJECTED"}
        ))

    def test_incomplete_recheck_blocks(self):
        self.assertFalse(sdk_continuation_complete(
            {"evaluation": "PRELIMINARY_PASS"},
            {"status": "COMPLETED", "model_resumed": True,
             "financial_review_completed": False, "document_match": True},
        ))

    def test_completed_requires_document_match(self):
        handoff = {"status": "COMPLETED", "model_resumed": True,
                   "financial_review_completed": True, "document_match": False}
        self.assertFalse(sdk_continuation_complete({}, handoff))
        handoff["document_match"] = True
        self.assertTrue(sdk_continuation_complete({}, handoff))
