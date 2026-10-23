import json
import unittest
from types import SimpleNamespace
from financial_approval_preview import financial_approval_preview, inspect_financial_request
from live_financial_approval_decision import decide_live_financial_pause
from investigation_checkpoint import create_checkpoint, document_fingerprint


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.raw = SimpleNamespace(type='function_call', name='submit_financial_data',
            call_id='call_1', arguments=json.dumps(dict(company='Synthetic', fiscal_year=2025,
                currency='USD', units='millions', revenue_current=120, revenue_current_page=2)))
        self.request = SimpleNamespace(raw_item=self.raw)
        self.decisions = []
        self.state = SimpleNamespace(get_interruptions=lambda: [self.request],
            approve=lambda *args, **kwargs: self.decisions.append(True),
            reject=lambda *args, **kwargs: self.decisions.append(False))
        self.handoff = dict(status='AWAITING_APPROVAL', sdk_state=self.state,
            checkpoint=create_checkpoint(document_fingerprint(b'pdf'), {}, 0, 0, None, []))

    def test_preview_contains_figures_and_pages_without_sdk_objects(self):
        preview = financial_approval_preview(self.handoff)
        self.assertEqual(preview['metrics'][0]['Proposed'], 120)
        self.assertEqual(preview['metrics'][0]['PDF page'], 2)
        self.assertEqual(preview['metadata']['currency'], 'USD')
        self.assertEqual(set(preview), {'request_sha256', 'metadata', 'metrics'})
        json.dumps(preview, allow_nan=False)

    def test_changed_arguments_or_call_identity_cannot_use_previous_approval(self):
        for field, value in [('arguments', '{"revenue_current":130}'), ('call_id', 'other')]:
            with self.subTest(field=field):
                original = getattr(self.raw, field)
                fingerprint = financial_approval_preview(self.handoff)['request_sha256']
                setattr(self.raw, field, value)
                with self.assertRaisesRegex(ValueError, 'REQUEST_CHANGED'):
                    decide_live_financial_pause(self.handoff, b'pdf', True,
                        expected_request_sha256=fingerprint)
                self.assertEqual(self.decisions, [])
                self.assertEqual(self.handoff['status'], 'AWAITING_APPROVAL')
                setattr(self.raw, field, original)

    def test_unexpected_tool_is_blocked_before_sdk_mutation(self):
        self.raw.name = 'read_page'
        with self.assertRaisesRegex(ValueError, 'UNEXPECTED_FINANCIAL_APPROVAL_TOOL'):
            decide_live_financial_pause(self.handoff, b'pdf', True)
        self.assertEqual(self.decisions, [])

    def test_malformed_ambiguous_or_nonfinite_arguments_are_blocked(self):
        for arguments in ['not JSON', '[]', '{"revenue_current":NaN}',
                          '{"revenue_current":120,"revenue_current":130}',
                          '{"revenue_current":true}', '{"revenue_current":null}']:
            with self.subTest(arguments=arguments):
                self.raw.arguments = arguments
                with self.assertRaises(ValueError):
                    inspect_financial_request(self.request)

    def test_metric_preview_is_a_copy(self):
        preview = financial_approval_preview(self.handoff)
        preview['metrics'][0]['Proposed'] = 999
        self.assertEqual(financial_approval_preview(self.handoff)['metrics'][0]['Proposed'], 120)
