import unittest
from types import SimpleNamespace
from sdk_resume_gate import checked_resume_mode


class SDKResumeGateTests(unittest.TestCase):
    def setUp(self):
        self.state = SimpleNamespace(get_interruptions=lambda: [])
        self.model = SimpleNamespace(
            is_offline_scripted_model=True,
            get_response=lambda: None,
        )

    def test_fresh_run(self):
        self.assertEqual(checked_resume_mode(None, None, None, None), "FRESH_RUN")

    def test_offline_sdk_resume_allowed(self):
        self.assertEqual(
            checked_resume_mode({}, b"pdf", self.state, self.model),
            "OFFLINE_SDK_RESUME",
        )

    def test_paid_model_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "LIVE_RESUME_DISABLED"):
            checked_resume_mode({}, b"pdf", self.state, None)

    def test_missing_original_document_blocked(self):
        with self.assertRaisesRegex(ValueError, "RESUME_REQUIRES_ORIGINAL_PDF"):
            checked_resume_mode({}, None, self.state, self.model)

    def test_missing_checkpoint_blocked(self):
        with self.assertRaisesRegex(ValueError, "RESUME_CHECKPOINT_REQUIRED"):
            checked_resume_mode(None, b"pdf", self.state, self.model)


if __name__ == "__main__":
    unittest.main()
