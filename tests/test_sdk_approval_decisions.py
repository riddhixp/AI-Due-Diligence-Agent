import unittest
from types import SimpleNamespace
from approval_queue import prepare_approval_queue, decide_approval
from sdk_approval_decisions import apply_approval_decisions


class MockState:
    def __init__(self):
        self.requests = ["a", "b"]
        self.approvals = []
        self.rejections = []

    def get_interruptions(self):
        return list(self.requests)

    def approve(self, item, always_approve=False):
        self.approvals.append((item, always_approve))

    def reject(self, item, always_reject=False, *, rejection_message=None):
        self.rejections.append((item, always_reject, rejection_message))


class SDKApprovalDecisionTests(unittest.TestCase):
    def setUp(self):
        self.fingerprint = "a" * 64
        self.state = MockState()
        result = SimpleNamespace(interruptions=["a", "b"], to_state=lambda: self.state)
        self.queue = prepare_approval_queue(result, self.fingerprint)

    def test_approval_and_rejection_apply_once_without_running(self):
        decide_approval(self.queue, self.fingerprint, 0, True)
        decide_approval(self.queue, self.fingerprint, 1, False)
        result = apply_approval_decisions(self.queue, self.fingerprint)
        self.assertEqual(self.state.approvals, [("a", False)])
        self.assertEqual(self.state.rejections[0][:2], ("b", False))
        self.assertTrue(result["decisions_applied"])
        self.assertFalse(result["model_resumed"])
        with self.assertRaisesRegex(ValueError, "DECISIONS_ALREADY_APPLIED"):
            apply_approval_decisions(self.queue, self.fingerprint)

    def test_pending_decision_blocks_all_mutation(self):
        decide_approval(self.queue, self.fingerprint, 0, True)
        with self.assertRaisesRegex(ValueError, "UNDECIDED_APPROVALS"):
            apply_approval_decisions(self.queue, self.fingerprint)
        self.assertEqual(self.state.approvals, [])

    def test_mismatched_document_blocks_all_mutation(self):
        decide_approval(self.queue, self.fingerprint, 0, True)
        decide_approval(self.queue, self.fingerprint, 1, True)
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            apply_approval_decisions(self.queue, "b" * 64)
        self.assertEqual(self.state.approvals, [])

    def test_changed_request_count_rejected_before_mutation(self):
        decide_approval(self.queue, self.fingerprint, 0, True)
        decide_approval(self.queue, self.fingerprint, 1, True)
        self.state.requests.pop()
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUEST_COUNT_MISMATCH"):
            apply_approval_decisions(self.queue, self.fingerprint)
        self.assertEqual(self.state.approvals, [])


if __name__ == "__main__":
    unittest.main()
