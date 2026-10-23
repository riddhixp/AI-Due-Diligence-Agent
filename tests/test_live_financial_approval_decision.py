import unittest
from types import SimpleNamespace
from live_financial_approval_decision import decide_live_financial_pause
from investigation_checkpoint import document_fingerprint, create_checkpoint


class FakeState:
    def __init__(self):
        self.approved = 0
        self.rejected = 0

    def get_interruptions(self):
        return [SimpleNamespace(raw_item=SimpleNamespace(
            type="function_call", name="submit_financial_data", call_id="test_call",
            arguments='{"revenue_current":120}'))]

    def approve(self, item, always_approve=False):
        self.approved += 1

    def reject(self, item, always_reject=False, rejection_message=""):
        self.rejected += 1


class LiveApprovalDecisionTests(unittest.TestCase):
    def setUp(self):
        self.sdk = FakeState()
        self.doc = b"fixture pdf"
        self.handoff = {
            "status": "AWAITING_APPROVAL",
            "sdk_state": self.sdk,
            "checkpoint": create_checkpoint(document_fingerprint(self.doc), {}, 0, 0, None, []),
        }

    def test_accept_once(self):
        result = decide_live_financial_pause(self.handoff, self.doc, True)
        self.assertEqual(result["status"], "APPROVED")
        self.assertFalse(result["model_resumed"])
        self.assertEqual(self.sdk.approved, 1)
        with self.assertRaisesRegex(ValueError, "ALREADY_DECIDED"):
            decide_live_financial_pause(self.handoff, self.doc, True)

    def test_reject_once(self):
        result = decide_live_financial_pause(self.handoff, self.doc, False)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(self.sdk.rejected, 1)

    def test_wrong_pdf_does_not_mutate(self):
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            decide_live_financial_pause(self.handoff, b"other", True)
        self.assertEqual(self.sdk.approved, 0)

    def test_tampered_financial_history_blocks_approval(self):
        self.handoff["checkpoint"]["submission_count"] = 1
        with self.assertRaisesRegex(ValueError, "MISSING_SUBMISSION"):
            decide_live_financial_pause(self.handoff, self.doc, True)
        self.assertEqual(self.sdk.approved, 0)
        self.assertEqual(self.handoff["status"], "AWAITING_APPROVAL")

    def test_tampered_page_reads_blocks_approval(self):
        self.handoff["page_reads"] = 1
        self.handoff["reads_at_review"] = 0
        with self.assertRaisesRegex(ValueError, "PAUSE_READ_COUNTER_MISMATCH"):
            decide_live_financial_pause(self.handoff, self.doc, True)
        self.assertEqual(self.sdk.approved, 0)

    def test_invalid_sdk_state_rejected(self):
        self.handoff["sdk_state"] = object()
        with self.assertRaisesRegex(ValueError, "SDK_INTERRUPTION_UNAVAILABLE"):
            decide_live_financial_pause(self.handoff, self.doc, True)

    def test_copied_handoff_cannot_reverse_decision(self):
        copied = dict(self.handoff)
        decide_live_financial_pause(self.handoff, self.doc, True)
        with self.assertRaisesRegex(ValueError, "SDK_APPROVAL_ALREADY_DECIDED"):
            decide_live_financial_pause(copied, self.doc, False)
        self.assertEqual((self.sdk.approved, self.sdk.rejected), (1, 0))

    def test_concurrent_copied_handoffs_apply_only_one_decision(self):
        from concurrent.futures import ThreadPoolExecutor
        def attempt(index):
            try:
                return decide_live_financial_pause(dict(self.handoff), self.doc, index % 2 == 0)['status']
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(attempt, range(32)))
        self.assertEqual(outcomes.count('SDK_APPROVAL_ALREADY_DECIDED'), 31)
        self.assertEqual(self.sdk.approved + self.sdk.rejected, 1)

    def test_failed_sdk_decision_is_terminal_even_for_copy(self):
        copied = dict(self.handoff)
        def fail(*args, **kwargs):
            self.sdk.approved += 1
            raise RuntimeError('Decision may already have mutated state')
        self.sdk.approve = fail
        with self.assertRaises(RuntimeError):
            decide_live_financial_pause(self.handoff, self.doc, True)
        self.assertEqual(self.handoff['status'], 'FAILED')
        with self.assertRaisesRegex(ValueError, 'SDK_APPROVAL_ALREADY_DECIDED'):
            decide_live_financial_pause(copied, self.doc, False)
        self.assertEqual((self.sdk.approved, self.sdk.rejected), (1, 0))

    def test_changed_request_does_not_consume_decision(self):
        with self.assertRaisesRegex(ValueError, 'FINANCIAL_APPROVAL_REQUEST_CHANGED'):
            decide_live_financial_pause(self.handoff, self.doc, True,
                                        expected_request_sha256='stale')
        self.assertEqual(self.handoff['status'], 'AWAITING_APPROVAL')
        decide_live_financial_pause(self.handoff, self.doc, True)
        self.assertEqual(self.sdk.approved, 1)

    def test_sdk_cancellation_marks_decision_failed(self):
        import asyncio
        def cancel(*args, **kwargs):
            raise asyncio.CancelledError()
        self.sdk.approve = cancel
        with self.assertRaises(asyncio.CancelledError):
            decide_live_financial_pause(self.handoff, self.doc, True)
        self.assertEqual(self.handoff['status'], 'FAILED')

    def test_tracking_does_not_retain_transcript(self):
        import gc
        import weakref
        from live_financial_approval_decision import _decided_states
        decide_live_financial_pause(self.handoff, self.doc, True)
        state_id = id(self.sdk)
        reference = weakref.ref(self.sdk)
        del self.sdk
        self.handoff.clear()
        gc.collect()
        self.assertIsNone(reference())
        self.assertNotIn(state_id, _decided_states)
