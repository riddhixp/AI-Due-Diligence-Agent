import unittest
from sdk_offline_approval_demo import start_sdk_offline_approval, decide_sdk_offline_approval


class SDKOfflineApprovalInterfaceTests(unittest.TestCase):
    def test_sdk_pause_approved_without_model_continuation(self):
        queue = start_sdk_offline_approval(b"test synthetic PDF")
        self.assertTrue(queue["ready"])
        self.assertEqual(len(queue["state"].get_interruptions()), 1)
        result = decide_sdk_offline_approval(queue, b"test synthetic PDF", True)
        self.assertEqual(result["approvals"], ["APPROVED"])
        self.assertTrue(result["sdk_decision_applied"])
        self.assertFalse(result["model_resumed"])
        self.assertEqual(result["api_calls"], 0)

    def test_sdk_pause_rejected_without_tool_execution(self):
        queue = start_sdk_offline_approval(b"test PDF")
        result = decide_sdk_offline_approval(queue, b"test PDF", False)
        self.assertEqual(result["approvals"], ["REJECTED"])
        self.assertFalse(result["can_resume"])

    def test_document_change_rejected(self):
        queue = start_sdk_offline_approval(b"one")
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            decide_sdk_offline_approval(queue, b"two", True)


if __name__ == "__main__":
    unittest.main()
