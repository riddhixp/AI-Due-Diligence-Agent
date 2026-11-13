import unittest
from types import SimpleNamespace
from approval_queue import prepare_approval_queue, decide_approval
from approval_handoff import prepare_approval_handoff


class ApprovalHandoffTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64
        state = SimpleNamespace(get_interruptions=lambda: ["one"])
        result = SimpleNamespace(interruptions=["one"], to_state=lambda: state)
        self.queue = prepare_approval_queue(result, self.digest)

    def test_undecided_request_cannot_handoff(self):
        self.assertEqual(
            prepare_approval_handoff(self.queue, self.digest)["reason"],
            "UNDECIDED_APPROVALS",
        )

    def test_approved_request_is_manifest_only(self):
        decide_approval(self.queue, self.digest, 0, True)
        handoff = prepare_approval_handoff(self.queue, self.digest)
        self.assertEqual(handoff["decisions"], ["APPROVED"])
        self.assertFalse(handoff["can_resume"])
        self.assertNotIn("state", handoff)

    def test_rejected_request_is_manifest_only(self):
        decide_approval(self.queue, self.digest, 0, False)
        self.assertEqual(
            prepare_approval_handoff(self.queue, self.digest)["decisions"],
            ["REJECTED"],
        )

    def test_document_mismatch(self):
        decide_approval(self.queue, self.digest, 0, True)
        self.assertEqual(
            prepare_approval_handoff(self.queue, "b" * 64)["reason"],
            "DOCUMENT_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
