import unittest
import json
import tempfile
from io import BytesIO
from pathlib import Path
from pypdf import PdfWriter
from unittest.mock import patch
from scripts.create_conflict_test_fixture import create_conflict_fixture
from types import SimpleNamespace
from financial_approval_preview import pending_financial_request
from live_continuation_preflight import preflight_live_continuation
from investigation_checkpoint import create_checkpoint, document_fingerprint


class FakeSDKState:
    def __init__(self):
        self.arguments = '{"revenue_current":120}'

    def get_interruptions(self):
        return [SimpleNamespace(raw_item=SimpleNamespace(type='function_call',
            name='submit_financial_data', call_id='preflight_call', arguments=self.arguments))]


class ContinuationPreflightTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as folder:
            self.pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        self.handoff = {
            "status": "APPROVED",
            "live_resume_enabled": False,
            "sdk_state": FakeSDKState(),
            "checkpoint": create_checkpoint(
                document_fingerprint(self.pdf),
                {"revenue_current": 120}, 1, 1,
                "PRELIMINARY_CHECKS_PASSED",
                ["submit_financial_data", "review_submitted_financials"],
            ),
        }

        self.handoff['decision_request_sha256'] = pending_financial_request(self.handoff['sdk_state'])[2]

    def test_approved_preflight_only(self):
        result = preflight_live_continuation(self.handoff, self.pdf)
        self.assertEqual(result["submission_count"], 1)
        self.assertEqual(result["reviewed_count"], 1)
        self.assertFalse(result["ready_for_paid_resume"])
        self.assertEqual(result["reason"], "PAID_CONTINUATION_DISABLED")
        self.assertFalse(result["model_resumed"])
        self.assertEqual(result["document_page_count"], 2)
        self.assertTrue(result["document_readable"])
        self.assertTrue(result["approved_citations_in_range"])

    def test_inconsistent_saved_read_counters(self):
        self.handoff["page_reads"] = 2
        self.handoff["reads_at_review"] = 0
        with self.assertRaisesRegex(ValueError, "PAUSE_READ_COUNTER_MISMATCH"):
            preflight_live_continuation(self.handoff, self.pdf)

    def test_wrong_document(self):
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            preflight_live_continuation(self.handoff, b"other")

    def test_rejected_approval(self):
        self.handoff["status"] = "REJECTED"
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUIRED"):
            preflight_live_continuation(self.handoff, self.pdf)

    def test_tampered_financial_trace(self):
        self.handoff["checkpoint"]["tool_calls"] = []
        with self.assertRaisesRegex(ValueError, "TRACE_COUNT_MISMATCH"):
            preflight_live_continuation(self.handoff, self.pdf)

    def test_missing_or_malformed_receipt_is_not_approved_preflight(self):
        for value in [None, '', 'invalid', True]:
            self.handoff['decision_request_sha256'] = value
            with self.assertRaisesRegex(ValueError, 'MISSING_FINANCIAL_DECISION_RECEIPT'):
                preflight_live_continuation(self.handoff, self.pdf)

    def test_changed_approved_request_is_rejected_without_mutation(self):
        self.handoff['sdk_state'].arguments = '{"revenue_current":130}'
        with self.assertRaisesRegex(ValueError, 'FINANCIAL_APPROVAL_REQUEST_CHANGED'):
            preflight_live_continuation(self.handoff, self.pdf)
        self.assertEqual(self.handoff['status'], 'APPROVED')
        self.assertFalse(self.handoff['live_resume_enabled'])

    def test_missing_pending_request_cannot_use_old_receipt(self):
        self.handoff['sdk_state'].get_interruptions = lambda: []
        with self.assertRaisesRegex(ValueError, 'FINANCIAL_APPROVAL_REQUEST_CHANGED'):
            preflight_live_continuation(self.handoff, self.pdf)

    def test_approved_out_of_document_citations_fail_without_mutation(self):
        for field in ['source_page', 'revenue_current_page', 'operating_cash_flow_page']:
            self.handoff['sdk_state'].arguments = json.dumps({'revenue_current': 120, field: 3})
            self.handoff['decision_request_sha256'] = pending_financial_request(self.handoff['sdk_state'])[2]
            with self.subTest(field=field), patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
                with self.assertRaisesRegex(ValueError, 'FINANCIAL_APPROVAL_PAGE_OUT_OF_RANGE'):
                    preflight_live_continuation(self.handoff, self.pdf)
            self.assertEqual(self.handoff['status'], 'APPROVED')
            self.assertFalse(self.handoff['live_resume_enabled'])

    def test_out_of_document_read_history_fails(self):
        checkpoint = self.handoff['checkpoint']
        checkpoint['tool_calls'].append('read_page')
        checkpoint['page_read_events'] = [{'tool_index': 2, 'page': 3}]
        with self.assertRaisesRegex(ValueError, 'INVALID_PAGE_READ_HISTORY'):
            preflight_live_continuation(self.handoff, self.pdf)

    def test_bound_unreadable_or_invalid_pdf_cannot_pass_preflight(self):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buffer = BytesIO()
        writer.write(buffer)
        for pdf in [b'not a pdf', buffer.getvalue()]:
            with self.subTest(blank=pdf != b'not a pdf'):
                self.handoff['checkpoint']['document_sha256'] = document_fingerprint(pdf)
                with self.assertRaisesRegex(ValueError, 'READABLE_PDF_REQUIRED'):
                    preflight_live_continuation(self.handoff, pdf)
                self.assertEqual(self.handoff['status'], 'APPROVED')

    def test_in_range_citations_need_no_model_call(self):
        self.handoff['sdk_state'].arguments = '{"revenue_current":120,"source_page":2,"revenue_current_page":1}'
        self.handoff['decision_request_sha256'] = pending_financial_request(self.handoff['sdk_state'])[2]
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            result = preflight_live_continuation(self.handoff, self.pdf)
        self.assertEqual(result['api_calls'], 0)
        self.assertTrue(result['approved_citations_in_range'])
        self.assertFalse(result['ready_for_paid_resume'])
