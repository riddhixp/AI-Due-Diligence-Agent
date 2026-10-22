import unittest
from sdk_offline_approval_demo import (
    start_sdk_offline_approval, decide_sdk_offline_approval,
    resume_sdk_offline_approval,
)


class OfflineSDKResumeUITests(unittest.TestCase):
    def test_approved_tool_executes_once_on_real_sdk_resume(self):
        pdf = b"fixture"
        queue = start_sdk_offline_approval(pdf)
        decide_sdk_offline_approval(queue, pdf, True)
        out = resume_sdk_offline_approval(queue, pdf)
        self.assertTrue(out["finished"])
        self.assertEqual(out["executed_submissions"], [120])
        self.assertEqual(out["external_api_calls"], 0)
        with self.assertRaisesRegex(ValueError, "ALREADY_RESUMED"):
            resume_sdk_offline_approval(queue, pdf)

    def test_rejection_skips_tool_but_sdk_continues(self):
        pdf = b"fixture"
        queue = start_sdk_offline_approval(pdf)
        decide_sdk_offline_approval(queue, pdf, False)
        out = resume_sdk_offline_approval(queue, pdf)
        self.assertTrue(out["finished"])
        self.assertEqual(out["executed_submissions"], [])

    def test_undecided_run_is_blocked(self):
        pdf = b"fixture"
        queue = start_sdk_offline_approval(pdf)
        with self.assertRaisesRegex(ValueError, "SDK_APPROVAL_NOT_APPLIED"):
            resume_sdk_offline_approval(queue, pdf)

    def test_different_pdf_is_blocked(self):
        pdf = b"fixture"
        queue = start_sdk_offline_approval(pdf)
        decide_sdk_offline_approval(queue, pdf, True)
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            resume_sdk_offline_approval(queue, b"other")
