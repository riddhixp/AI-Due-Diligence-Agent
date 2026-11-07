import unittest
from types import SimpleNamespace
from sdk_pause_capture import capture_approval_pause, pause_public_status


class SDKPauseCaptureTests(unittest.TestCase):
    def test_no_approval_is_not_pause(self):
        self.assertFalse(capture_approval_pause(SimpleNamespace(interruptions=[]))["paused"])

    def test_genuine_approval_state_captured_only_in_memory(self):
        state = SimpleNamespace(get_interruptions=lambda: ["approval"])
        result = SimpleNamespace(interruptions=["approval"], to_state=lambda: state)
        capture = capture_approval_pause(result)
        self.assertTrue(capture["paused"])
        self.assertIs(capture["state"], state)
        self.assertNotIn("state", pause_public_status(capture))
        self.assertFalse(pause_public_status(capture)["can_resume"])

    def test_missing_export_is_rejected(self):
        result = SimpleNamespace(interruptions=["approval"])
        self.assertEqual(capture_approval_pause(result)["reason"], "SDK_STATE_EXPORT_UNAVAILABLE")

    def test_lost_approvals_is_rejected(self):
        state = SimpleNamespace(get_interruptions=lambda: [])
        result = SimpleNamespace(interruptions=["approval"], to_state=lambda: state)
        self.assertEqual(capture_approval_pause(result)["reason"], "PAUSE_APPROVALS_NOT_PRESERVED")

    def test_export_failure_is_safe(self):
        def fails():
            raise RuntimeError("sensitive details")
        result = SimpleNamespace(interruptions=["approval"], to_state=fails)
        capture = capture_approval_pause(result)
        self.assertEqual(capture["reason"], "SDK_STATE_EXPORT_FAILED")
        self.assertNotIn("sensitive", str(pause_public_status(capture)))


if __name__ == "__main__":
    unittest.main()
