"""Exercise normal-run completion locally; no provider model can be contacted."""
import json
import unittest
from unittest.mock import patch
from agents import Agent, Runner, set_tracing_disabled
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from due_diligence_engine import run_due_diligence
from scripted_offline_model import ScriptedOfflineModel
from synthetic_financial_fixture import PAGES, conflict_submission_arguments


class FreshCompletionBoundaryTests(unittest.TestCase):
    def run_local(self, final_output='Synthetic completed review.', skip_review=False,
                  revenue_previous=100):
        set_tracing_disabled(True)
        model = ScriptedOfflineModel()
        fields = conflict_submission_arguments(source_page=1, revenue_current_page=1,
            revenue_previous_page=1, gross_profit_page=1, net_income_page=1,
            revenue_previous=revenue_previous)
        def call(name, args, index):
            return [ResponseFunctionToolCall(id=f'fresh_f{index}', call_id=f'fresh_c{index}',
                type='function_call', name=name, arguments=json.dumps(args), status='completed')]
        model.responses = [call('read_page', {'page_number': 1}, 1),
                           call('submit_financial_data', fields, 2)]
        if not skip_review:
            model.responses.append(call('review_submitted_financials', {}, 3))
        model.responses.append([ResponseOutputMessage(id='fresh_m', type='message', role='assistant',
            status='completed', content=[ResponseOutputText(type='output_text',
            text='Scripted placeholder.', annotations=[])])])
        def local_agent(*args, **kwargs):
            kwargs['model'] = model
            return Agent(*args, **kwargs)
        run = Runner.run_sync
        def finish(*args, **kwargs):
            result = run(*args, **kwargs)
            result.final_output = final_output
            return result
        # Exercise FRESH_RUN with an exact local model injected at construction.
        # Any accidental provider request or tracing traffic fails the test.
        with patch('due_diligence_engine.Agent', side_effect=local_agent), \
             patch('due_diligence_engine.Runner.run_sync', side_effect=finish), \
             patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            pages = [page.replace('Total revenue 120 100 90',
                     f'Total revenue 120 {revenue_previous} 90') for page in PAGES]
            return run_due_diligence(pages)

    def test_completed_fresh_run_has_explicit_completion(self):
        report, validation, _, evaluation = self.run_local()
        self.assertTrue(evaluation['final_eligible'])
        self.assertTrue(evaluation['final_response_complete'])
        self.assertIs(evaluation['simulation'], False)
        self.assertIsNotNone(validation)
        self.assertIn('Synthetic completed review.', report)

    def test_unreviewed_fresh_run_uses_incomplete_report(self):
        report, validation, financial, evaluation = self.run_local(skip_review=True)
        self.assertFalse(evaluation['final_eligible'])
        self.assertIsNone(validation)
        self.assertEqual(financial['revenue_current'], 120)
        self.assertIn('Investigation incomplete', report)
        self.assertNotIn('Synthetic completed review.', report)

    def test_empty_final_response_cannot_be_hidden_by_generated_appendix(self):
        for value in [None, '', '  \n\t', {}, 123]:
            with self.subTest(final_output=value):
                report, validation, _, evaluation = self.run_local(final_output=value)
                self.assertFalse(evaluation['final_eligible'])
                self.assertFalse(evaluation['final_response_complete'])
                self.assertIn('FINAL_RESPONSE_MISSING', evaluation['issues'])
                self.assertIsNone(validation)
                self.assertIn('Investigation incomplete', report)

    def test_zero_prior_revenue_finishes_as_incomplete_without_crashing(self):
        report, validation, financial, evaluation = self.run_local(revenue_previous=0)
        self.assertFalse(evaluation['final_eligible'])
        self.assertEqual(evaluation['financial_evidence'], 'NEEDS_REVIEW')
        self.assertEqual(financial['revenue_previous'], 0)
        self.assertIsNone(validation)
        self.assertIn('Investigation incomplete', report)

    def test_nonfinite_submission_is_not_accepted(self):
        for value in [float('nan'), float('inf')]:
            with self.subTest(value=value):
                report, validation, financial, evaluation = self.run_local(revenue_previous=value)
                self.assertEqual(financial, {})
                self.assertIsNone(validation)
                self.assertFalse(evaluation['final_eligible'])
                self.assertIn('Investigation incomplete', report)
