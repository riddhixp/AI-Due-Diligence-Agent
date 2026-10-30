import copy
import unittest
from unittest.mock import patch
from cached_analysis_review import recheck_cached_analysis
from final_artifact_policy import final_report_eligible
from report_verification import finalise_dd_report
from synthetic_financial_fixture import PAGES, supported_submission


class CachedAnalysisReviewTests(unittest.TestCase):
    def test_old_pass_banner_is_replaced_when_optional_evidence_fails(self):
        financial = supported_submission()
        financial['operating_cash_flow'] = 999
        financial['source_pages']['operating_cash_flow'] = 1
        saved = {'report': finalise_dd_report('# Original findings', financial,
                 {'status': 'PRELIMINARY_CHECKS_PASSED'}), 'financial_data': financial}
        original = copy.deepcopy(saved)
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            result = recheck_cached_analysis(saved, PAGES)
        self.assertIn('Financial evidence not fully verified', result['report'])
        self.assertNotIn('**Preliminary checks passed.', result['report'])
        self.assertTrue(result['report'].endswith('# Original findings'))
        self.assertEqual(result['agent_evaluation']['financial_evidence'], 'NEEDS_REVIEW')
        self.assertEqual(saved, original)

    def test_current_checks_do_not_invent_original_investigation_history(self):
        result = recheck_cached_analysis({'report': '# Findings',
                                         'financial_data': supported_submission()}, PAGES)
        evaluation = result['agent_evaluation']
        self.assertEqual(evaluation['financial_evidence'], 'PRELIMINARY_CHECKS_PASSED')
        self.assertFalse(evaluation['original_tool_history_restored'])
        self.assertFalse(final_report_eligible(evaluation))
        self.assertEqual(evaluation['api_calls'], 0)

    def test_falsy_malformed_cached_financials_are_flagged_not_silently_missing(self):
        for financial in (None, False, 0, '', [], ()):
            with self.subTest(financial=financial):
                result = recheck_cached_analysis(
                    {'report': '# Preserved narrative', 'financial_data': financial}, PAGES)
                self.assertEqual(result['financial_data'], {})
                self.assertIsNone(result['validation'])
                self.assertIn('INVALID_CACHED_FINANCIALS', result['agent_evaluation']['issues'])
                self.assertFalse(final_report_eligible(result['agent_evaluation']))
                self.assertTrue(result['report'].endswith('# Preserved narrative'))

    def test_malformed_saved_figures_cannot_restore_verified_status(self):
        for financial in [{'revenue_current': 120}, ['invalid']]:
            with self.subTest(financial=financial):
                result = recheck_cached_analysis({'report': '# Old findings',
                                                  'financial_data': financial}, PAGES)
                self.assertEqual(result['financial_data'], {})
                self.assertIsNone(result['validation'])
                self.assertFalse(result['agent_evaluation']['final_eligible'])
                self.assertIn('INVALID_CACHED_FINANCIALS', result['agent_evaluation']['issues'])

    def test_changed_review_banner_is_idempotent(self):
        old = finalise_dd_report('# Findings', supported_submission(),
                                 {'status': 'PRELIMINARY_CHECKS_PASSED'})
        new = finalise_dd_report(old, supported_submission(), {'status': 'NEEDS_REVIEW'})
        self.assertEqual(finalise_dd_report(new, supported_submission(), {'status': 'NEEDS_REVIEW'}), new)
        self.assertEqual(new.count('## Evidence verification status'), 1)

    def test_invalid_required_numbers_are_cleared_before_dashboard_display(self):
        for value in [None, True, '120', float('nan'), float('inf')]:
            with self.subTest(value=value):
                financial = supported_submission()
                financial['revenue_current'] = value
                result = recheck_cached_analysis({'report': '# Findings', 'financial_data': financial}, PAGES)
                self.assertEqual(result['financial_data'], {})
                self.assertIsNone(result['validation'])
                self.assertIn('INVALID_CACHED_FINANCIALS', result['agent_evaluation']['issues'])

    def test_zero_prior_revenue_cache_retains_figures_with_unavailable_growth(self):
        financial = supported_submission()
        financial['revenue_previous'] = 0
        pages = [PAGES[0].replace('Total revenue 120 100 90', 'Total revenue 120 0 90')]
        result = recheck_cached_analysis({'report': '# Findings', 'financial_data': financial}, pages)
        self.assertEqual(result['financial_data']['revenue_previous'], 0)
        self.assertEqual(result['validation']['revenue_growth']['status'], 'UNAVAILABLE')
        self.assertEqual(result['agent_evaluation']['financial_evidence'], 'NEEDS_REVIEW')
        self.assertFalse(final_report_eligible(result['agent_evaluation']))

    def test_invalid_narrative_is_rejected_before_evidence_review(self):
        for report in [None, '', '  \n ', False, 123, ['Findings'], {'text': 'Findings'}]:
            with self.subTest(report=report):
                saved = {'report': report, 'financial_data': supported_submission()}
                original = copy.deepcopy(saved)
                with patch('cached_analysis_review.review_financial_evidence') as review:
                    with self.assertRaisesRegex(ValueError, 'INVALID_SAVED_ANALYSIS'):
                        recheck_cached_analysis(saved, PAGES)
                    review.assert_not_called()
                self.assertEqual(saved, original)

    def test_missing_narrative_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'INVALID_SAVED_ANALYSIS'):
            recheck_cached_analysis({'financial_data': supported_submission()}, PAGES)

    def test_invalid_cached_metadata_is_cleared_before_dashboard_formatting(self):
        invalid = [('fiscal_year', value) for value in [None, True, '2025', 'bad', 2025.5, 0, 10000]]
        invalid += [(field, value) for field in ['company', 'currency', 'units']
                    for value in [None, True, 123, ['USD'], {'text': 'USD'}]]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                financial = supported_submission()
                financial[field] = value
                result = recheck_cached_analysis({'report': '# Findings', 'financial_data': financial}, PAGES)
                self.assertEqual(result['financial_data'], {})
                self.assertIsNone(result['validation'])
                self.assertIn('INVALID_CACHED_FINANCIALS', result['agent_evaluation']['issues'])
                self.assertTrue(result['report'].endswith('# Findings'))

    def test_blank_cached_financial_labels_do_not_reach_dashboard(self):
        for field in ('company', 'currency', 'units'):
            for value in ('', '   ', '\n\t'):
                with self.subTest(field=field, value=repr(value)):
                    financial = supported_submission()
                    financial[field] = value
                    result = recheck_cached_analysis(
                        {'report': '# Retained narrative', 'financial_data': financial}, PAGES)
                    self.assertEqual(result['financial_data'], {})
                    self.assertIsNone(result['validation'])
                    self.assertIn('INVALID_CACHED_FINANCIALS',
                                  result['agent_evaluation']['issues'])
                    self.assertTrue(result['report'].endswith('# Retained narrative'))
                    self.assertFalse(final_report_eligible(result['agent_evaluation']))

    def test_all_optional_cached_metrics_require_finite_numeric_values(self):
        from optional_statement_metrics import OPTIONAL_STATEMENT_METRICS
        for field, *_ in OPTIONAL_STATEMENT_METRICS:
            for value in [True, '123', [], float('inf'), float('nan')]:
                with self.subTest(field=field, value=value):
                    financial = supported_submission()
                    financial[field] = value
                    result = recheck_cached_analysis({'report': '# Findings', 'financial_data': financial}, PAGES)
                    self.assertEqual(result['financial_data'], {})
                    self.assertIsNone(result['validation'])
                    self.assertFalse(result['agent_evaluation']['final_eligible'])

    def test_unestablished_text_metadata_remains_an_evidence_issue(self):
        financial = supported_submission()
        financial['units'] = 'unknown'
        result = recheck_cached_analysis({'report': '# Findings', 'financial_data': financial}, PAGES)
        self.assertEqual(result['financial_data'], financial)
        self.assertEqual(result['agent_evaluation']['financial_evidence'], 'NEEDS_REVIEW')
        self.assertNotIn('INVALID_CACHED_FINANCIALS', result['agent_evaluation']['issues'])
