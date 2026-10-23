"""End-to-end real SDK handoff -> app tools -> review, using no paid model."""
import json
import unittest
from io import BytesIO
from agents import Agent, Runner, function_tool, set_tracing_disabled
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from reportlab.pdfgen import canvas
from financial_approval_resume import decide_and_resume_offline
from live_financial_pause_handoff import make_financial_pause_handoff
from scripted_offline_model import ScriptedOfflineModel
from synthetic_financial_fixture import PAGES


def call(name, args, index):
    return [ResponseFunctionToolCall(id=f'f{index}', call_id=f'c{index}',
            type='function_call', name=name, arguments=json.dumps(args), status='completed')]


class ApprovalResumeTests(unittest.TestCase):
    def setUp(self):
        set_tracing_disabled(True)
        out = BytesIO()
        pdf = canvas.Canvas(out)
        text = pdf.beginText(40, 780)
        for line in PAGES[0].splitlines():
            text.textLine(line)
        pdf.drawText(text)
        pdf.save()
        self.pdf = out.getvalue()
        self.model = ScriptedOfflineModel()
        fields = dict(company='Synthetic Company', fiscal_year=2025, currency='USD',
                      units='millions', revenue_current=120, revenue_previous=100,
                      gross_profit=80, net_income=30, reported_revenue_growth=20,
                      reported_gross_margin=66.67, reported_net_margin=25,
                      source_page=1, revenue_current_page=1, revenue_previous_page=1,
                      gross_profit_page=1, net_income_page=1)
        self.fields = fields
        self.model.responses = [call('submit_financial_data', fields, 1),
            call('review_submitted_financials', {}, 2),
            [ResponseOutputMessage(id='m1', type='message', role='assistant',
                status='completed', content=[ResponseOutputText(type='output_text',
                text='Synthetic financial review completed.', annotations=[])])]]

        @function_tool(needs_approval=True)
        def submit_financial_data() -> str:
            """Request approval; the resumed app must replace this closure."""
            raise AssertionError('Old financial closure executed')

        initial = Runner.run_sync(Agent(name='AI Due Diligence Analyst', model=self.model,
                                  tools=[submit_financial_data]), 'Synthetic request')
        self.handoff = make_financial_pause_handoff(
            {'paused': True, 'state': initial.to_state()}, self.pdf, {}, 0, 0,
            None, ['read_page'], 1, 0)

    def test_approval_runs_real_app_submission_and_review(self):
        result = decide_and_resume_offline(self.handoff, self.pdf, True, self.model)
        self.assertEqual(result['status'], 'COMPLETED_OFFLINE')
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertEqual(result['evaluation']['financial_evidence'], 'PRELIMINARY_CHECKS_PASSED')
        self.assertTrue(result['evaluation']['final_eligible'])
        self.assertEqual(result['external_api_calls'], 0)
        self.assertEqual(self.model.calls, 3)

    def test_rejection_cannot_create_verified_report(self):
        result = decide_and_resume_offline(self.handoff, self.pdf, False, self.model)
        self.assertEqual(result['financial'], {})
        self.assertFalse(result['evaluation']['final_eligible'])

    def test_duplicate_dispatch_is_rejected(self):
        decide_and_resume_offline(self.handoff, self.pdf, True, self.model)
        with self.assertRaisesRegex(ValueError, 'ALREADY_CLAIMED'):
            decide_and_resume_offline(self.handoff, self.pdf, True, self.model)
        self.assertEqual(self.model.calls, 3)

    def test_paid_model_refused_before_decision(self):
        with self.assertRaisesRegex(ValueError, 'LIVE_RESUME_DISABLED'):
            decide_and_resume_offline(self.handoff, self.pdf, True, 'gpt-5-mini')
        self.assertEqual(self.handoff['status'], 'AWAITING_APPROVAL')
        self.assertEqual(self.model.calls, 1)

    def test_other_document_refused_before_decision(self):
        with self.assertRaisesRegex(ValueError, 'DOCUMENT_MISMATCH'):
            decide_and_resume_offline(self.handoff, b'other pdf', True, self.model)
        self.assertEqual(self.handoff['status'], 'AWAITING_APPROVAL')

    def test_another_approval_pause_preserves_progress(self):
        self.model.responses.insert(1, call('submit_financial_data', self.fields, 3))
        paused = decide_and_resume_offline(self.handoff, self.pdf, True, self.model)
        self.assertEqual(paused['status'], 'AWAITING_APPROVAL')
        self.assertEqual(self.handoff['status'], 'PAUSED_AGAIN')
        next_handoff = paused['handoff']
        self.assertEqual(next_handoff['checkpoint']['submission_count'], 1)
        self.assertEqual(next_handoff['checkpoint']['reviewed_count'], 1)
        result = decide_and_resume_offline(next_handoff, self.pdf, False, self.model)
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertEqual(result['status'], 'COMPLETED_OFFLINE')

    def test_runner_failure_consumes_handoff(self):
        self.model.responses = []
        with self.assertRaisesRegex(AssertionError, 'Unexpected further model'):
            decide_and_resume_offline(self.handoff, self.pdf, True, self.model)
        self.assertEqual(self.handoff['status'], 'FAILED')
        with self.assertRaisesRegex(ValueError, 'ALREADY_CLAIMED'):
            decide_and_resume_offline(self.handoff, self.pdf, True, self.model)

    def test_scripted_result_cannot_be_exported_as_real_final_report(self):
        from final_artifact_policy import final_report_eligible
        result = decide_and_resume_offline(self.handoff, self.pdf, True, self.model)
        self.assertTrue(result['evaluation']['simulation'])
        self.assertFalse(final_report_eligible(result['evaluation']))

    def test_concurrent_decisions_dispatch_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        import app  # Initialize Streamlit on the test thread before workers.
        def attempt(_):
            try:
                return decide_and_resume_offline(
                    self.handoff, self.pdf, True, self.model)['status']
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(16)))
        self.assertEqual(results.count('COMPLETED_OFFLINE'), 1)
        self.assertEqual(results.count('APPROVAL_RESUME_ALREADY_CLAIMED'), 15)
        self.assertEqual(self.model.calls, 3)

    def test_cancelled_resume_is_terminal(self):
        import asyncio
        from unittest.mock import patch
        with patch('due_diligence_engine.run_due_diligence', side_effect=asyncio.CancelledError()):
            with self.assertRaises(asyncio.CancelledError):
                decide_and_resume_offline(self.handoff, self.pdf, True, self.model)
        self.assertEqual(self.handoff['status'], 'FAILED')
        with self.assertRaisesRegex(ValueError, 'ALREADY_CLAIMED'):
            decide_and_resume_offline(self.handoff, self.pdf, True, self.model)
        self.assertEqual(self.model.calls, 1)
