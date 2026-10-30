import unittest
from live_financial_pause_handoff import (
    SDKFinancialApprovalPaused, make_financial_pause_handoff,
    public_financial_pause_status,
)


class LiveFinancialPauseHandoffTests(unittest.TestCase):
    def test_handoff_preserves_sdk_state_and_safe_checkpoint(self):
        sdk_state = object()
        pause = {"paused": True, "state": sdk_state}
        result = make_financial_pause_handoff(
            pause, b"%PDF-synthetic", {"revenue_current": 130},
            1, 0, None, ["read_page", "submit_financial_data", "read_page"], 2, 0,
        )
        self.assertIs(result["sdk_state"], sdk_state)
        self.assertEqual(result["checkpoint"]["submission_count"], 1)
        self.assertFalse(result["checkpoint"]["model_conversation_saved"])
        self.assertFalse(result["live_resume_enabled"])
        status = public_financial_pause_status(result)
        self.assertNotIn("sdk_state", status)
        self.assertNotIn("financial_data", status)
        self.assertEqual(status["page_reads"], 2)
        self.assertEqual(status["status"], "AWAITING_APPROVAL")
        error = SDKFinancialApprovalPaused(result)
        self.assertIs(error.handoff["sdk_state"], sdk_state)
        self.assertNotIn("revenue_current", str(error))

    def test_mismatched_trace_read_counters_refused(self):
        with self.assertRaisesRegex(ValueError, "PAUSE_READ_COUNTER_MISMATCH"):
            make_financial_pause_handoff(
                {"paused": True, "state": object()}, b"pdf",
                {"revenue_current": 130}, 1, 0, None,
                ["submit_financial_data"], 1, 0,
            )

    def test_missing_pdf_refused(self):
        with self.assertRaisesRegex(ValueError, "ORIGINAL_PDF_REQUIRED"):
            make_financial_pause_handoff(
                {"paused": True, "state": object()}, b"", {}, 0, 0,
                None, [], 0, 0,
            )

    def test_invalid_counters_refused(self):
        with self.assertRaisesRegex(ValueError, "INVALID_PAGE_READ_COUNTERS"):
            make_financial_pause_handoff(
                {"paused": True, "state": object()}, b"pdf", {}, 1, 0,
                None, [], 0, 2,
            )

    def test_no_sdk_pause_refused(self):
        with self.assertRaisesRegex(ValueError, "NO_CAPTURED_SDK_APPROVAL"):
            make_financial_pause_handoff(
                {"paused": False, "state": None}, b"pdf", {}, 0, 0,
                None, [], 0, 0,
            )
