"""Click the actual Streamlit controls; no paid model or network permitted."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from scripts.create_conflict_test_fixture import create_conflict_fixture


class CorrectionWorkflowUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        path = create_conflict_fixture(Path(self.folder.name) / 'fixture.pdf')
        self.pdf_path = path
        # Render the component without the file uploader so AppTest can drive it.
        self.app = AppTest.from_string(f'''
import streamlit as st
from pathlib import Path
from correction_workflow_ui import render_correction_workflow
st.session_state.setdefault('report', 'Existing real analysis')
render_correction_workflow(st, Path({str(path)!r}).read_bytes())
''', default_timeout=20)
        block = patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        block.start()
        self.addCleanup(block.stop)
        self.app.run()

    def click(self, key):
        self.app.button(key=key).click().run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.error)

    def test_two_approval_clicks_complete_without_touching_existing_analysis(self):
        self.click('app_workflow_start')
        self.click('app_workflow_approve')
        session = self.app.session_state['offline_application_workflow']
        self.assertEqual(session['handoff']['checkpoint']['review_status'], 'NEEDS_REVIEW')
        frame = self.app.dataframe[0].value
        row = frame[frame['Metric'] == 'Revenue current'].iloc[0]
        self.assertEqual(list(row['Previous PDF pages']), [2])
        self.assertEqual(list(row['PDF pages']), [2])
        self.assertEqual(row['Change'], 'Changed')
        self.click('app_workflow_approve')
        result = self.app.session_state['offline_application_workflow']['result']
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertTrue(result['evaluation']['simulation'])
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')
        self.assertEqual(len(self.app.get('download_button')), 0)
        self.assertFalse(any(button.key == 'app_workflow_approve' for button in self.app.button))
        self.click('app_workflow_discard')
        self.assertNotIn('offline_application_workflow', self.app.session_state)

    def test_reject_correction_keeps_failed_source_review_visible(self):
        self.click('app_workflow_start')
        self.click('app_workflow_approve')
        self.click('app_workflow_reject')
        result = self.app.session_state['offline_application_workflow']['result']
        self.assertEqual(result['financial']['revenue_current'], 130)
        self.assertFalse(result['evaluation']['final_eligible'])

    def test_changed_document_clears_pending_session(self):
        self.click('app_workflow_start')
        self.pdf_path.write_bytes(self.pdf_path.read_bytes() + b'changed')
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertNotIn('offline_application_workflow', self.app.session_state)
        self.assertFalse(any(button.key == 'app_workflow_approve' for button in self.app.button))

    def test_declined_initial_request_ends_without_financial_submission(self):
        self.click('app_workflow_start')
        self.click('app_workflow_reject')
        result = self.app.session_state['offline_application_workflow']['result']
        self.assertEqual(result['financial'], {})
        self.assertFalse(result['evaluation']['final_eligible'])
        self.assertFalse(any(button.key == 'app_workflow_approve' for button in self.app.button))

    def test_changed_request_requires_reviewing_refreshed_preview(self):
        import json
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        from agents import Agent, Runner, function_tool
        from scripted_offline_model import ScriptedOfflineModel
        from openai.types.responses import ResponseFunctionToolCall
        raw = session['handoff']['sdk_state'].get_interruptions()[0].raw_item
        fields = json.loads(raw.arguments)
        fields['revenue_current'] = 131
        replacement = ScriptedOfflineModel()
        replacement.responses = [[ResponseFunctionToolCall(
            id='replacement_f', call_id='replacement_c', type='function_call',
            name='submit_financial_data', arguments=json.dumps(fields), status='completed')]] + session['model'].responses

        @function_tool(needs_approval=True)
        def submit_financial_data() -> str:
            """Create an alternate genuine pause to exercise stale preview detection."""
            raise AssertionError('Old closure must never execute')

        paused = Runner.run_sync(Agent(name='AI Due Diligence Analyst', model=replacement,
                                 tools=[submit_financial_data]), 'Changed proposal')
        session['handoff']['sdk_state'] = paused.to_state()
        session['model'] = replacement
        self.app.button(key='app_workflow_approve').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('REQUEST_CHANGED' in error.value for error in self.app.error))
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['model'].calls, 1)
        frame = self.app.dataframe[0].value
        row = frame[frame['Metric'] == 'Revenue current'].iloc[0]
        self.assertEqual(row['Proposed'], 131)
        self.click('app_workflow_approve')
        self.assertEqual(session['handoff']['checkpoint']['financial_data']['revenue_current'], 131)

    def test_source_evidence_is_available_before_any_approval(self):
        self.click('app_workflow_start')
        evidence = ' '.join(item.value for item in self.app.text)
        self.assertIn('Total revenue 120 100 90', evidence)
        self.assertIn('Fiscal years 2025 2024 2023', evidence)
        self.assertIn('authoritative FY2025 total revenue figure is 120', evidence)
        session = self.app.session_state['offline_application_workflow']
        self.assertEqual(session['model'].calls, 2)
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['handoff']['checkpoint']['submission_count'], 0)

    def test_source_recovery_uses_three_approvals_and_preserves_real_report(self):
        self.app.selectbox(key='app_workflow_scenario').select('Recover after unrelated source read').run()
        self.click('app_workflow_start')
        self.click('app_workflow_approve')
        self.click('app_workflow_approve')
        session = self.app.session_state['offline_application_workflow']
        self.assertEqual(session['handoff']['checkpoint']['submission_count'], 1)
        self.assertEqual(session['handoff']['checkpoint']['financial_data']['revenue_current'], 130)
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.click('app_workflow_approve')
        result = session['result']
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertTrue(result['evaluation']['final_eligible'])
        self.assertTrue(result['evaluation']['simulation'])
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')
        self.assertEqual(len(self.app.get('download_button')), 0)

    def test_invalid_preview_remains_discardable(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        # Corrupt SDK-owned state, since public interruption previews are copies.
        session['handoff']['sdk_state']._current_step.interruptions[0].raw_item.arguments = 'not JSON'
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.error)
        self.assertFalse(any(button.key == 'app_workflow_approve' for button in self.app.button))
        self.app.button(key='app_workflow_discard').click().run()
        self.assertNotIn('offline_application_workflow', self.app.session_state)
        self.assertFalse(self.app.error)
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')

    def test_terminal_continuation_failure_removes_decision_controls(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        session['model'].responses = []
        self.app.button(key='app_workflow_approve').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(session['handoff']['status'], 'FAILED')
        self.assertTrue(any('Offline continuation failed' in item.value for item in self.app.error))
        self.assertFalse(any(button.key in ('app_workflow_approve', 'app_workflow_reject')
                             for button in self.app.button))
        self.assertNotIn('result', session)
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')
        self.click('app_workflow_start')
        replacement = self.app.session_state['offline_application_workflow']
        self.assertEqual(replacement['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertIsNot(replacement['handoff']['sdk_state'], session['handoff']['sdk_state'])
        self.assertNotIn('workflow_error', replacement)

    def test_incomplete_rehearsal_has_warning_instead_of_success(self):
        self.click('app_workflow_start')
        self.click('app_workflow_reject')
        self.assertFalse(self.app.success)
        self.assertTrue(any('ended with incomplete checks' in item.value for item in self.app.warning))
        self.assertEqual(len(self.app.get('download_button')), 0)

    def test_failure_before_decision_stays_visible_without_automatic_retry(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        with patch('correction_workflow_ui.decide_and_resume_offline', side_effect=OSError('Local failure')) as resume:
            self.app.button(key='app_workflow_approve').click().run()
            self.assertEqual(resume.call_count, 1)
        self.assertFalse(self.app.exception)
        self.assertTrue(any('could not start' in item.value for item in self.app.error))
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['model'].calls, 2)
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')
        self.click('app_workflow_approve')
        self.assertEqual(session['handoff']['checkpoint']['submission_count'], 1)

    def test_rejection_failure_before_decision_preserves_script(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        responses = list(session['model'].responses)
        with patch('correction_workflow_ui.decide_and_resume_offline', side_effect=OSError('Local failure')):
            self.app.button(key='app_workflow_reject').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['model'].responses, responses)
        self.click('app_workflow_approve')
        self.assertEqual(session['handoff']['checkpoint']['submission_count'], 1)
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
