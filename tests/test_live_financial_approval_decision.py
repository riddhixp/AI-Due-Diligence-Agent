import unittest
from live_financial_approval_decision import decide_live_financial_pause
from investigation_checkpoint import document_fingerprint, create_checkpoint


class FakeState:
    def __init__(self):
        self.approved = 0
        self.rejected = 0

    def get_interruptions(self):
        return [object()]

    def approve(self, item, always_approve=False):
        self.approved += 1

    def reject(self, item, always_reject=False, rejection_message=""):
        self.rejected += 1


class LiveApprovalDecisionTests(unittest.TestCase):
    def setUp(self):
        self.sdk = FakeState()
        self.doc = b"fixture pdf"
        self.handoff = {
            "status": "AWAITING_APPROVAL",
            "sdk_state": self.sdk,
            "checkpoint": create_checkpoint(document_fingerprint(self.doc), {}, 0, 0, None, []),
        }

    def test_accept_once(self):
        result = decide_live_financial_pause(self.handoff, self.doc, True)
        self.assertEqual(result["status"], "APPROVED")
        self.assertFalse(result["model_resumed"])
        self.assertEqual(self.sdk.approved, 1)
        with self.assertRaisesRegex(ValueError, "ALREADY_DECIDED"):
            decide_live_financial_pause(self.handoff, self.doc, True)

    def test_reject_once(self):
        result = decide_live_financial_pause(self.handoff, self.doc, False)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(self.sdk.rejected, 1)

    def test_wrong_pdf_does_not_mutate(self):
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            decide_live_financial_pause(self.handoff, b"other", True)
        self.assertEqual(self.sdk.approved, 0)

    def test_tampered_financial_history_blocks_approval(self):
        self.handoff["checkpoint"]["submission_count"] = 1
        with self.assertRaisesRegex(ValueError, "SUBMISSION_TRACE_COUNT_MISMATCH"):
            decide_live_financial_pause(self.handoff, self.doc, True)
        self.assertEqual(self.sdk.approved, 0)
        self.assertEqual(self.handoff["status"], "AWAITING_APPROVAL")

    def test_tampered_page_reads_blocks_approval(self):
        self.handoff["page_reads"] = 1
        self.handoff["reads_at_review"] = 0
        with self.assertRaisesRegex(ValueError, "PAUSE_READ_COUNTER_MISMATCH"):
            decide_live_financial_pause(self.handoff, self.doc, True)
        self.assertEqual(self.sdk.approved, 0)

    def test_invalid_sdk_state_rejected(self):
        self.handoff["sdk_state"] = object()
        with self.assertRaisesRegex(ValueError, "SDK_INTERRUPTION_UNAVAILABLE"):
            decide_live_financial_pause(self.handoff, self.doc, True)
