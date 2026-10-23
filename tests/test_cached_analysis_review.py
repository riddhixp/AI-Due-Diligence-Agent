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
