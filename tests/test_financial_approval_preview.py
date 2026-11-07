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
        self.assertEqual(set(preview), {'request_sha256', 'metadata', 'previous_metadata', 'metrics'})
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

    def test_ratio_preview_uses_all_input_pages_without_inventing_primary_citation(self):
        fields = dict(revenue_current=120, revenue_current_page=2, revenue_previous=100,
                      revenue_previous_page=3, reported_revenue_growth=20, source_page=99)
        self.raw.arguments = json.dumps(fields)
        preview = financial_approval_preview(self.handoff)
        ratio = next(row for row in preview['metrics'] if row['Metric'] == 'Reported revenue growth')
        self.assertIsNone(ratio['PDF page'])
        self.assertEqual(ratio['PDF pages'], [2, 3])
        self.assertEqual(ratio['Evidence'], 'Calculate from cited inputs')

    def test_optional_figure_omitted_by_correction_is_shown_as_removed(self):
        self.handoff['checkpoint']['financial_data'] = {
            'operating_cash_flow': 60, 'source_pages': {'operating_cash_flow': 4}}
        preview = financial_approval_preview(self.handoff)
        row = next(row for row in preview['metrics'] if row['Metric'] == 'Operating cash flow')
        self.assertEqual(row['Previous'], 60)
        self.assertIsNone(row['Proposed'])
        self.assertEqual(row['Change'], 'Removed')
        self.assertEqual(row['Previous PDF pages'], [4])
        self.assertEqual(row['PDF pages'], [])

    def test_previous_metadata_and_changed_citation_are_visible(self):
        self.handoff['checkpoint']['financial_data'] = dict(currency='GBP', units='thousands',
            fiscal_year=2024, revenue_current=120, source_pages={'revenue_current': 1})
        preview = financial_approval_preview(self.handoff)
        row = preview['metrics'][0]
        self.assertEqual(row['Previous PDF pages'], [1])
        self.assertEqual(row['PDF pages'], [2])
        self.assertEqual(row['Change'], 'Changed')
        self.assertEqual(preview['previous_metadata']['currency'], 'GBP')
        self.assertEqual(preview['metadata']['currency'], 'USD')

    def test_missing_optional_citation_does_not_fall_back_to_primary_page(self):
        self.raw.arguments = json.dumps(dict(revenue_current=120, operating_cash_flow=60, source_page=2))
        preview = financial_approval_preview(self.handoff)
        row = next(row for row in preview['metrics'] if row['Metric'] == 'Operating cash flow')
        self.assertEqual(row['PDF pages'], [])
        self.assertIsNone(row['PDF page'])

    def test_fractional_or_nonpositive_pages_are_rejected_before_decision(self):
        for value in [1.5, 1.0, 0, -1, None]:
            with self.subTest(page=value):
                self.raw.arguments = json.dumps(dict(revenue_current=120, revenue_current_page=value))
                with self.assertRaisesRegex(ValueError, 'INVALID_FINANCIAL_PAGE'):
                    decide_live_financial_pause(self.handoff, b'pdf', True)
                self.assertEqual(self.decisions, [])
                self.assertEqual(self.handoff['status'], 'AWAITING_APPROVAL')

    def test_invalid_years_and_unknown_arguments_are_rejected(self):
        for field, value in [('fiscal_year', 2025.5), ('fiscal_year', 0),
                             ('fiscal_year', None), ('unrecognized_amount', 99)]:
            with self.subTest(field=field, value=value):
                self.raw.arguments = json.dumps({'revenue_current': 120, field: value})
                with self.assertRaises(ValueError):
                    inspect_financial_request(self.request)

    def test_blank_metadata_and_null_required_values_are_rejected(self):
        for field, value in [('company', None), ('currency', '  '), ('units', ''),
                             ('gross_profit', None), ('reported_net_margin', None)]:
            self.raw.arguments = json.dumps({'revenue_current': 120, field: value})
            with self.assertRaises(ValueError):
                inspect_financial_request(self.request)

    def test_deeply_nested_json_is_a_controlled_invalid_request(self):
        self.raw.arguments = '{"revenue_current":120,"nested":' + '[' * 1500 + '0' + ']' * 1500 + '}'
        with self.assertRaises(ValueError):
            inspect_financial_request(self.request)
        from unittest.mock import patch
        with patch('financial_approval_preview.json.loads', side_effect=RecursionError()):
            with self.assertRaisesRegex(ValueError, 'INVALID_FINANCIAL_ARGUMENTS'):
                inspect_financial_request(self.request)

    def test_optional_null_pairs_remain_valid(self):
        self.raw.arguments = json.dumps(dict(revenue_current=120,
            operating_cash_flow=None, operating_cash_flow_page=None))
        values, _ = inspect_financial_request(self.request)
        self.assertIsNone(values['operating_cash_flow'])
