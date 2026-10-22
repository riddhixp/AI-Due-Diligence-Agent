import unittest
from investigation_checkpoint import create_checkpoint, document_fingerprint
from resume_preflight import resume_preflight


class ResumePreflightTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"fixture"
        self.checkpoint = create_checkpoint(
            document_fingerprint(self.pdf), {"revenue_current": 130},
            1, 0, None, ["submit_financial_data"],
        )
        self.transcript = [{"type": "message", "role": "user", "content": "hello"}]

    def test_no_transcript_saved(self):
        result = resume_preflight(self.checkpoint, self.pdf, self.transcript)
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "MODEL_CONVERSATION_NOT_SAVED")

    def test_document_mismatch(self):
        self.assertEqual(
            resume_preflight(self.checkpoint, b"different", self.transcript)["reason"],
            "DOCUMENT_MISMATCH",
        )

    def test_pending_call_rejected(self):
        pending = [{"type": "function_call", "call_id": "x"}]
        self.assertEqual(
            resume_preflight(self.checkpoint, self.pdf, pending)["reason"],
            "PENDING_TOOL_CALL",
        )

    def test_even_saved_history_is_not_mistaken_for_live_resume(self):
        self.checkpoint["model_conversation_saved"] = True
        result = resume_preflight(self.checkpoint, self.pdf, self.transcript)
        self.assertEqual(result["reason"], "TOOL_STATE_REBINDING_NOT_IMPLEMENTED")
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
