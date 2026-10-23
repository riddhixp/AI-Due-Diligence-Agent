import unittest
from live_continuation_preflight import preflight_live_continuation
from investigation_checkpoint import create_checkpoint, document_fingerprint


class FakeSDKState:
    def get_interruptions(self):
        return []


class ContinuationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"synthetic pdf"
        self.handoff = {
            "status": "APPROVED",
            "live_resume_enabled": False,
            "sdk_state": FakeSDKState(),
            "checkpoint": create_checkpoint(
                document_fingerprint(self.pdf),
                {"revenue_current": 120}, 1, 1,
                "PRELIMINARY_CHECKS_PASSED",
                ["submit_financial_data", "review_submitted_financials"],
            ),
        }

    def test_approved_preflight_only(self):
        result = preflight_live_continuation(self.handoff, self.pdf)
        self.assertEqual(result["submission_count"], 1)
        self.assertEqual(result["reviewed_count"], 1)
        self.assertFalse(result["ready_for_paid_resume"])
        self.assertEqual(result["reason"], "PAID_CONTINUATION_DISABLED")
        self.assertFalse(result["model_resumed"])

    def test_inconsistent_saved_read_counters(self):
        self.handoff["page_reads"] = 2
        self.handoff["reads_at_review"] = 0
        with self.assertRaisesRegex(ValueError, "PAUSE_READ_COUNTER_MISMATCH"):
            preflight_live_continuation(self.handoff, self.pdf)

    def test_wrong_document(self):
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            preflight_live_continuation(self.handoff, b"other")

    def test_rejected_approval(self):
        self.handoff["status"] = "REJECTED"
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUIRED"):
            preflight_live_continuation(self.handoff, self.pdf)

    def test_tampered_financial_trace(self):
        self.handoff["checkpoint"]["tool_calls"] = []
        with self.assertRaisesRegex(ValueError, "TRACE_COUNT_MISMATCH"):
            preflight_live_continuation(self.handoff, self.pdf)
