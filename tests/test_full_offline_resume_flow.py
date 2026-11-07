"""Offline end-to-end approval -> restored state -> mocked continuation tests.

These tests deliberately never import or call the real OpenAI Runner.
"""
import unittest
from types import SimpleNamespace

from approval_queue import prepare_approval_queue, decide_approval
from sdk_approval_decisions import apply_approval_decisions
from approved_run_handoff import prepare_approved_run_handoff
from offline_sdk_resume import dry_run_resume
from investigation_checkpoint import create_checkpoint, document_fingerprint


class FakePausedState:
    def __init__(self):
        self.actions = []
        self.requests = ["financial-submission"]

    def get_interruptions(self):
        return list(self.requests)

    def approve(self, request, always_approve=False):
        self.actions.append(("approved", request))

    def reject(self, request, always_reject=False, rejection_message=None):
        self.actions.append(("rejected", request))


class FakeRunner:
    offline_test_double = True

    def __init__(self):
        self.calls = []

    def run(self, agent, state):
        self.calls.append((agent, state))
        return "OFFLINE_ONLY"


class FullOfflineResumeFlowTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"synthetic offline fixture"
        self.digest = document_fingerprint(self.pdf)
        self.state = FakePausedState()
        self.result = SimpleNamespace(
            interruptions=["financial-submission"],
            to_state=lambda: self.state,
        )
        self.queue = prepare_approval_queue(self.result, self.digest)
        self.checkpoint = create_checkpoint(
            self.digest, {"revenue_current": 130, "revenue_previous": 100},
            1, 0, None, ["read_page", "submit_financial_data"],
        )
        self.agent = object()
        self.runner = FakeRunner()

    def test_approval_to_mock_execution_preserves_unreviewed_submission(self):
        decide_approval(self.queue, self.digest, 0, True)
        apply_approval_decisions(self.queue, self.digest)
        handoff = prepare_approved_run_handoff(
            self.queue, self.digest, self.checkpoint, self.pdf,
        )
        output = dry_run_resume(handoff, self.agent, self.runner)
        self.assertEqual(self.state.actions, [("approved", "financial-submission")])
        self.assertEqual(self.runner.calls, [(self.agent, self.state)])
        self.assertEqual(output["submissions_preserved"], 1)
        self.assertEqual(output["reviews_preserved"], 0)
        self.assertFalse(output["model_resumed"])

    def test_rejected_approval_never_reaches_runner(self):
        decide_approval(self.queue, self.digest, 0, False)
        apply_approval_decisions(self.queue, self.digest)
        with self.assertRaisesRegex(ValueError, "REJECTED_OR_MISSING_APPROVAL"):
            prepare_approved_run_handoff(
                self.queue, self.digest, self.checkpoint, self.pdf,
            )
        self.assertEqual(self.runner.calls, [])
        self.assertEqual(self.state.actions, [("rejected", "financial-submission")])

    def test_invalid_pdf_blocks_handoff_after_decision(self):
        decide_approval(self.queue, self.digest, 0, True)
        apply_approval_decisions(self.queue, self.digest)
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            prepare_approved_run_handoff(
                self.queue, self.digest, self.checkpoint, b"different document",
            )
        self.assertEqual(self.runner.calls, [])

    def test_unreviewed_state_stays_unreviewed(self):
        decide_approval(self.queue, self.digest, 0, True)
        apply_approval_decisions(self.queue, self.digest)
        handoff = prepare_approved_run_handoff(
            self.queue, self.digest, self.checkpoint, self.pdf,
        )
        self.assertEqual(handoff["financial_state"]["review_state"]["reviewed_count"], 0)
        self.assertIsNone(handoff["financial_state"]["review_state"]["status"])
        self.assertFalse(handoff["ready_for_live_run"])


if __name__ == "__main__":
    unittest.main()
