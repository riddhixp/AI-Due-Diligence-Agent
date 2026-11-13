import unittest
from offline_approval_demo import start_offline_approval, finish_offline_approval


class OfflineApprovalUITests(unittest.TestCase):
    def test_approval_persists_across_calls(self):
        queue = start_offline_approval(b"fixture")
        result = finish_offline_approval(queue, b"fixture", True)
        self.assertEqual(result["approvals"], ["APPROVED"])
        self.assertFalse(result["can_resume"])

    def test_rejection_and_document_mismatch(self):
        queue = start_offline_approval(b"fixture")
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            finish_offline_approval(queue, b"other", False)
        result = finish_offline_approval(queue, b"fixture", False)
        self.assertEqual(result["approvals"], ["REJECTED"])

    def test_duplicate_decision_blocked(self):
        queue = start_offline_approval(b"fixture")
        finish_offline_approval(queue, b"fixture", True)
        with self.assertRaisesRegex(ValueError, "APPROVAL_ALREADY_DECIDED"):
            finish_offline_approval(queue, b"fixture", True)


if __name__ == "__main__":
    unittest.main()
