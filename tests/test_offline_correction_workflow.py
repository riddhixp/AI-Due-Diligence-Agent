"""Exercise two approvals and evidence correction through the actual app."""
import tempfile
import unittest
from pathlib import Path
from scripts.create_conflict_test_fixture import create_conflict_fixture
from offline_correction_workflow import start_offline_correction_workflow
from financial_approval_resume import decide_and_resume_offline
from final_artifact_policy import final_report_eligible


class FullCorrectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        network = patch("socket.socket.connect", side_effect=AssertionError("NETWORK_FORBIDDEN"))
        network.start()
        self.addCleanup(network.stop)
        with tempfile.TemporaryDirectory() as folder:
            self.pdf = create_conflict_fixture(Path(folder) / 'conflict.pdf').read_bytes()
        self.session = start_offline_correction_workflow(self.pdf)

    def approve_initial(self):
        return decide_and_resume_offline(self.session['handoff'], self.pdf,
                                         True, self.session['model'])

    def test_two_approvals_correct_revenue_and_preserve_source_history(self):
        paused = self.approve_initial()
        self.assertEqual(paused['status'], 'AWAITING_APPROVAL')
        handoff = paused['handoff']
        checkpoint = handoff['checkpoint']
        self.assertEqual(checkpoint['financial_data']['revenue_current'], 130)
        self.assertEqual(checkpoint['submission_count'], 1)
        self.assertEqual(checkpoint['reviewed_count'], 1)
        self.assertEqual(checkpoint['review_status'], 'NEEDS_REVIEW')
        self.assertEqual(checkpoint['tool_calls'], [
            'read_page', 'submit_financial_data', 'review_submitted_financials', 'read_page'])
        self.assertEqual(handoff['page_reads'], 2)
        self.assertEqual(handoff['reads_at_review'], 1)
        result = decide_and_resume_offline(handoff, self.pdf, True, self.session['model'])
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertEqual(result['financial']['source_pages']['revenue_current'], 2)
        self.assertEqual(result['evaluation']['evaluation'], 'PRELIMINARY_PASS')
        self.assertTrue(result['evaluation']['final_eligible'])
        self.assertFalse(final_report_eligible(result['evaluation']))
        self.assertEqual(self.session['model'].calls, 7)

    def test_declined_correction_keeps_original_unverified_figures(self):
        paused = self.approve_initial()
        result = decide_and_resume_offline(paused['handoff'], self.pdf,
                                          False, self.session['model'])
        self.assertEqual(result['financial']['revenue_current'], 130)
        self.assertFalse(result['evaluation']['final_eligible'])
        self.assertIsNone(result['validation'])
        self.assertIn('Investigation incomplete', result['report'])

    def test_changed_pdf_cannot_approve_correction(self):
        paused = self.approve_initial()
        calls = self.session['model'].calls
        with self.assertRaisesRegex(ValueError, 'DOCUMENT_MISMATCH'):
            decide_and_resume_offline(paused['handoff'], self.pdf + b'changed',
                                      True, self.session['model'])
        self.assertEqual(self.session['model'].calls, calls)
        self.assertEqual(paused['handoff']['status'], 'AWAITING_APPROVAL')

    def test_other_pdf_cannot_start_rehearsal(self):
        with self.assertRaisesRegex(ValueError, 'SYNTHETIC_CONFLICT_PDF_REQUIRED'):
            start_offline_correction_workflow(b'not a pdf')

    def test_repeated_review_survives_second_approval_pause(self):
        from openai.types.responses import ResponseFunctionToolCall
        self.session['model'].responses.insert(1, [ResponseFunctionToolCall(
            id='repeat_f', call_id='repeat_c', type='function_call',
            name='review_submitted_financials', arguments='{}', status='completed')])
        paused = self.approve_initial()
        checkpoint = paused['handoff']['checkpoint']
        self.assertEqual(checkpoint['reviewed_count'], 1)
        self.assertEqual(checkpoint['tool_calls'].count('review_submitted_financials'), 2)
        result = decide_and_resume_offline(paused['handoff'], self.pdf,
                                          True, self.session['model'])
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertTrue(result['evaluation']['final_eligible'])

    def test_review_after_declined_initial_figures_does_not_poison_checkpoint(self):
        paused = decide_and_resume_offline(self.session['handoff'], self.pdf,
                                          False, self.session['model'])
        self.assertEqual(paused['status'], 'AWAITING_APPROVAL')
        checkpoint = paused['handoff']['checkpoint']
        self.assertEqual(checkpoint['submission_count'], 0)
        self.assertEqual(checkpoint['reviewed_count'], 0)
        self.assertIsNone(checkpoint['review_status'])
        self.assertIn('review_without_submission', checkpoint['tool_calls'])
        result = decide_and_resume_offline(paused['handoff'], self.pdf,
                                          True, self.session['model'])
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertEqual(result['status'], 'COMPLETED_OFFLINE')

    def test_pause_after_unreviewed_correction_preserves_new_figures(self):
        import json
        from openai.types.responses import ResponseFunctionToolCall
        from synthetic_financial_fixture import conflict_submission_arguments
        paused = self.approve_initial()
        self.session['model'].responses.insert(0, [ResponseFunctionToolCall(
            id='extra_f', call_id='extra_c', type='function_call',
            name='submit_financial_data',
            arguments=json.dumps(conflict_submission_arguments(revenue_current=999)),
            status='completed')])
        next_pause = decide_and_resume_offline(paused['handoff'], self.pdf,
                                               True, self.session['model'])
        checkpoint = next_pause['handoff']['checkpoint']
        self.assertEqual(checkpoint['submission_count'], 2)
        self.assertEqual(checkpoint['reviewed_count'], 1)
        self.assertIsNone(checkpoint['review_status'])
        self.assertEqual(checkpoint['financial_data']['revenue_current'], 120)
        result = decide_and_resume_offline(next_pause['handoff'], self.pdf,
                                          True, self.session['model'])
        # Even an explicit approval cannot bypass the two-submission tool limit.
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertFalse(result['evaluation']['final_eligible'])

    def test_unrelated_page_read_cannot_authorize_correction_after_resume(self):
        import json
        # The post-review reread now visits page 1, while correction cites page 2.
        self.session['model'].responses[1][0].arguments = json.dumps({'page_number': 1})
        paused = self.approve_initial()
        checkpoint = paused['handoff']['checkpoint']
        self.assertEqual(checkpoint['page_read_events'],
                         [{'tool_index': 0, 'page': 2}, {'tool_index': 3, 'page': 1}])
        result = decide_and_resume_offline(paused['handoff'], self.pdf, True, self.session['model'])
        self.assertEqual(result['financial']['revenue_current'], 130)
        self.assertFalse(result['evaluation']['final_eligible'])
        self.assertIsNone(result['validation'])

    def test_missing_legacy_page_history_requires_new_source_read(self):
        paused = self.approve_initial()
        paused['handoff']['checkpoint'].pop('page_read_events')
        result = decide_and_resume_offline(paused['handoff'], self.pdf, True, self.session['model'])
        self.assertEqual(result['financial']['revenue_current'], 130)
        self.assertFalse(result['evaluation']['final_eligible'])

    def test_cited_source_reread_survives_approval_pause(self):
        paused = self.approve_initial()
        self.assertEqual(paused['handoff']['checkpoint']['page_read_events'],
                         [{'tool_index': 0, 'page': 2}, {'tool_index': 3, 'page': 2}])
        result = decide_and_resume_offline(paused['handoff'], self.pdf, True, self.session['model'])
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertTrue(result['evaluation']['final_eligible'])

    def test_refused_correction_recovers_without_consuming_slot(self):
        session = start_offline_correction_workflow(self.pdf, scenario='source_recovery')
        first = decide_and_resume_offline(session['handoff'], self.pdf, True, session['model'])
        retry = decide_and_resume_offline(first['handoff'], self.pdf, True, session['model'])
        checkpoint = retry['handoff']['checkpoint']
        self.assertEqual(checkpoint['submission_count'], 1)
        self.assertEqual(checkpoint['reviewed_count'], 1)
        self.assertEqual(checkpoint['financial_data']['revenue_current'], 130)
        self.assertEqual(checkpoint['review_status'], 'NEEDS_REVIEW')
        self.assertEqual(checkpoint['page_read_events'][-2:],
                         [{'tool_index': 3, 'page': 1}, {'tool_index': 5, 'page': 2}])
        result = decide_and_resume_offline(retry['handoff'], self.pdf, True, session['model'])
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertTrue(result['evaluation']['final_eligible'])
        self.assertFalse(final_report_eligible(result['evaluation']))
        self.assertEqual(session['model'].calls, 9)

    def test_unknown_rehearsal_scenario_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_OFFLINE_WORKFLOW_SCENARIO'):
            start_offline_correction_workflow(self.pdf, scenario='unknown')

    def test_recovery_with_missing_sdk_review_trace_cannot_complete(self):
        from agents import Runner
        from unittest.mock import patch
        session = start_offline_correction_workflow(self.pdf, scenario='source_recovery')
        first = decide_and_resume_offline(session['handoff'], self.pdf, True, session['model'])
        retry = decide_and_resume_offline(first['handoff'], self.pdf, True, session['model'])
        run = Runner.run_sync
        def incomplete_trace(*args, **kwargs):
            result = run(*args, **kwargs)
            result.new_items = [item for item in result.new_items
                if not (item.type == 'tool_call_item'
                        and getattr(item.raw_item, 'name', None) == 'review_submitted_financials')]
            return result
        with patch('due_diligence_engine.Runner.run_sync', side_effect=incomplete_trace):
            result = decide_and_resume_offline(retry['handoff'], self.pdf, True, session['model'])
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertEqual(result['evaluation']['financial_evidence'], 'PRELIMINARY_CHECKS_PASSED')
        self.assertIn('TOOL_TRACE_MISMATCH', result['evaluation']['issues'])
        self.assertFalse(result['evaluation']['final_eligible'])
        self.assertIsNone(result['validation'])
