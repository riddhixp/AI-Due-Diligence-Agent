import unittest
from types import SimpleNamespace
from approval_queue import prepare_approval_queue, decide_approval, approval_public_status


class ApprovalQueueTests(unittest.TestCase):
    def setUp(self):
        self.hash = "a" * 64
        self.state = SimpleNamespace(get_interruptions=lambda: ["pending"])
        self.result = SimpleNamespace(interruptions=["pending"], to_state=lambda: self.state)

    def test_queue_does_not_execute_or_resume(self):
        queue = prepare_approval_queue(self.result, self.hash)
        self.assertTrue(queue["ready"])
        self.assertFalse(queue["can_resume"])
        self.assertNotIn("state", approval_public_status(queue))

    def test_approve_once(self):
        queue = prepare_approval_queue(self.result, self.hash)
        decide_approval(queue, self.hash, 0, True)
        self.assertEqual(approval_public_status(queue)["approvals"], ["APPROVED"])
        with self.assertRaisesRegex(ValueError, "ALREADY_DECIDED"):
            decide_approval(queue, self.hash, 0, True)

    def test_rejection_is_recorded(self):
        queue = prepare_approval_queue(self.result, self.hash)
        decide_approval(queue, self.hash, 0, False)
        self.assertEqual(approval_public_status(queue)["approvals"], ["REJECTED"])

    def test_wrong_document_fails(self):
        queue = prepare_approval_queue(self.result, self.hash)
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            decide_approval(queue, "b" * 64, 0, True)

    def test_missing_sdk_pause_fails_closed(self):
        result = SimpleNamespace(interruptions=[])
        queue = prepare_approval_queue(result, self.hash)
        self.assertFalse(queue["ready"])
        self.assertEqual(queue["pending"], [])


if __name__ == "__main__":
    unittest.main()
