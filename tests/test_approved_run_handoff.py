import unittest
from types import SimpleNamespace
from approval_queue import prepare_approval_queue, decide_approval
from sdk_approval_decisions import apply_approval_decisions
from approved_run_handoff import prepare_approved_run_handoff
from investigation_checkpoint import create_checkpoint, document_fingerprint


class FakeRunState:
    def get_interruptions(self):
        return ["request"]

    def approve(self, request, always_approve=False):
        pass

    def reject(self, request, always_reject=False, rejection_message=None):
        pass


class ApprovedRunHandoffTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"fixture"
        self.digest = document_fingerprint(self.pdf)
        self.sdk = FakeRunState()
        result = SimpleNamespace(
            interruptions=["request"], to_state=lambda: self.sdk,
        )
        self.queue = prepare_approval_queue(result, self.digest)
        self.checkpoint = create_checkpoint(
            self.digest, {"revenue_current": 130}, 1, 0, None,
            ["read_page", "submit_financial_data"],
        )

    def apply(self):
        decide_approval(self.queue, self.digest, 0, True)
        apply_approval_decisions(self.queue, self.digest)

    def test_applied_decision_preserves_financial_state(self):
        self.apply()
        bundle = prepare_approved_run_handoff(
            self.queue, self.digest, self.checkpoint, self.pdf,
        )
        self.assertIs(bundle["sdk_state"], self.sdk)
        self.assertEqual(bundle["submission_count"], 1)
        self.assertEqual(bundle["reviewed_count"], 0)
        self.assertFalse(bundle["ready_for_live_run"])

    def test_unapplied_decision_rejected(self):
        with self.assertRaisesRegex(ValueError, "SDK_DECISIONS_NOT_APPLIED"):
            prepare_approved_run_handoff(
                self.queue, self.digest, self.checkpoint, self.pdf,
            )

    def test_mismatched_pdf_rejected(self):
        self.apply()
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            prepare_approved_run_handoff(
                self.queue, self.digest, self.checkpoint, b"different",
            )

    def test_handoff_does_not_mutate_checkpoint(self):
        self.apply()
        bundle = prepare_approved_run_handoff(
            self.queue, self.digest, self.checkpoint, self.pdf,
        )
        bundle["financial_state"]["financial_submission"]["revenue_current"] = 120
        self.assertEqual(self.checkpoint["financial_data"]["revenue_current"], 130)


if __name__ == "__main__":
    unittest.main()
