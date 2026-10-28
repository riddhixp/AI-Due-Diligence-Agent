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

    def test_corrupted_result_shows_safe_discard_instead_of_crashing(self):
        for broken in ([], {}, {'evaluation': None, 'financial': {}},
                       {'evaluation': {}, 'financial': None},
                       {'evaluation': {}, 'financial': {}},
                       {'evaluation': {'final_eligible': True}, 'financial': {}},
                       {'evaluation': {'final_eligible': 'true', 'financial_evidence': 'PASS'}, 'financial': {}},
                       {'evaluation': {'final_eligible': False, 'financial_evidence': None}, 'financial': {}}):
            with self.subTest(broken=broken):
                self.click('app_workflow_start')
                session = self.app.session_state['offline_application_workflow']
                session['result'] = broken
                self.app.run()
                self.assertFalse(self.app.exception)
                self.assertTrue(any('stored rehearsal result is invalid' in e.value
                                    for e in self.app.error))
                self.assertFalse(any(button.key == 'app_workflow_approve'
                                     for button in self.app.button))
                self.click('app_workflow_discard')
                self.assertNotIn('offline_application_workflow', self.app.session_state)
                self.assertEqual(self.app.session_state['report'], 'Existing real analysis')

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
        invalid = ['not JSON', '{"revenue_current":120,"nested":' + '[' * 1500 + '0' + ']' * 1500 + '}']
        for arguments in invalid:
            with self.subTest(argument_length=len(arguments)):
                self.click('app_workflow_start')
                session = self.app.session_state['offline_application_workflow']
                # Corrupt SDK-owned state; public interruption previews are copies.
                session['handoff']['sdk_state']._current_step.interruptions[0].raw_item.arguments = arguments
                self.app.run()
                self.assertFalse(self.app.exception)
                self.assertTrue(self.app.error)
                self.assertFalse(any(button.key == 'app_workflow_approve' for button in self.app.button))
                self.app.button(key='app_workflow_discard').click().run()
                self.assertNotIn('offline_application_workflow', self.app.session_state)
                self.assertFalse(self.app.error)
                self.assertEqual(self.app.session_state['report'], 'Existing real analysis')

    def test_corrupted_failed_checkpoint_is_safe_and_discardable(self):
        for broken in ([], {'submission_count': 1},
                       {'submission_count': '1', 'financial_data': {}},
                       {'submission_count': -1, 'financial_data': {}},
                       {'submission_count': 1, 'financial_data': None},
                       {'submission_count': 1, 'financial_data': {},
                        'review_status': []}):
            with self.subTest(broken=broken):
                self.click('app_workflow_start')
                session = self.app.session_state['offline_application_workflow']
                session['handoff']['status'] = 'FAILED'
                session['handoff']['failure_checkpoint'] = broken
                self.app.run()
                self.assertFalse(self.app.exception)
                self.assertTrue(any('Saved failure progress is incomplete' in item.value
                                    for item in self.app.warning))
                self.assertFalse(any(button.key in ('app_workflow_approve', 'app_workflow_reject')
                                     for button in self.app.button))
                self.assertEqual(len(self.app.get('download_button')), 0)
                self.click('app_workflow_discard')
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
        self.assertEqual(session['handoff']['failure_checkpoint']['submission_count'], 1)
        self.assertEqual(session['handoff']['failure_checkpoint']['financial_data']['revenue_current'], 130)
        visible = ' '.join(item.value for item in self.app.markdown)
        self.assertIn('Accepted submissions before failure:', visible)
        self.assertIn('Last accepted synthetic revenue:', visible)
        self.assertEqual(len(self.app.get('download_button')), 0)
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

    def test_optional_removal_is_visible_before_approval_and_stays_missing(self):
        self.app.selectbox(key='app_workflow_scenario').select('Remove unsupported cash flow').run()
        self.click('app_workflow_start')
        self.click('app_workflow_approve')
        frame = self.app.dataframe[0].value
        row = frame[frame['Metric'] == 'Operating cash flow'].iloc[0]
        self.assertEqual(row['Previous'], 999)
        self.assertEqual(row['Change'], 'Removed')
        self.assertEqual(list(row['Previous PDF pages']), [2])
        self.assertEqual(list(row['PDF pages']), [])
        self.click('app_workflow_approve')
        result = self.app.session_state['offline_application_workflow']['result']
        self.assertIsNone(result['financial']['operating_cash_flow'])
        self.assertIsNone(result['financial']['source_pages']['operating_cash_flow'])
        self.assertTrue(result['evaluation']['simulation'])
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')
        self.assertEqual(len(self.app.get('download_button')), 0)

    def test_unavailable_citation_cannot_be_approved_but_can_be_rejected(self):
        import json
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        from due_diligence_engine import run_due_diligence
        from live_financial_pause_handoff import SDKFinancialApprovalPaused
        from scripted_offline_model import ScriptedOfflineModel
        from synthetic_conflict_document import read_synthetic_conflict_pages
        from openai.types.responses import ResponseFunctionToolCall
        raw = session['handoff']['sdk_state'].get_interruptions()[0].raw_item
        fields = json.loads(raw.arguments)
        fields['revenue_current_page'] = 3
        model = ScriptedOfflineModel()
        model.responses = [[ResponseFunctionToolCall(id='unavailable_f', call_id='unavailable_c',
            type='function_call', name='submit_financial_data', arguments=json.dumps(fields),
            status='completed')]] + session['model'].responses
        pdf = self.pdf_path.read_bytes()
        with self.assertRaises(SDKFinancialApprovalPaused) as paused:
            run_due_diligence(read_synthetic_conflict_pages(pdf), offline_scripted_model=model,
                              financial_approval_required=True, pause_pdf_bytes=pdf)
        session['handoff'] = paused.exception.handoff
        session['model'] = model
        session.pop('displayed_request_sha256', None)
        self.app.run()
        self.assertTrue(any('page 3 is unavailable' in item.value for item in self.app.warning))
        self.app.button(key='app_workflow_approve').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('PAGE_OUT_OF_RANGE' in item.value for item in self.app.error))
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['model'].calls, 1)
        self.click('app_workflow_reject')
        self.assertEqual(session['result']['financial'], {})
        self.assertFalse(session['result']['evaluation']['final_eligible'])
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')

    def test_local_proposal_checks_are_visible_before_each_free_decision(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        self.assertTrue(any('Proposed figures need review' in item.value for item in self.app.warning))
        self.assertEqual(session['handoff']['checkpoint']['submission_count'], 0)
        self.assertEqual(session['model'].calls, 2)
        self.assertTrue(any('status' in frame.value.columns for frame in self.app.dataframe[1:]))
        self.click('app_workflow_approve')
        self.assertTrue(any('passed local preliminary checks' in item.value for item in self.app.info))
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['handoff']['checkpoint']['financial_data']['revenue_current'], 130)
        self.assertEqual(session['model'].calls, 5)
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')

    def test_local_check_failure_leaves_rehearsal_rejectable_and_discardable(self):
        with patch('proposed_financial_review_ui.review_proposed_financial_request',
                   side_effect=ValueError('LOCAL_REVIEW_UNAVAILABLE')):
            self.click('app_workflow_start')
            session = self.app.session_state['offline_application_workflow']
            self.assertTrue(any('Local checks are unavailable' in item.value for item in self.app.warning))
            self.assertEqual(session['handoff']['checkpoint']['submission_count'], 0)
            self.assertEqual(session['model'].calls, 2)
            self.click('app_workflow_reject')
        self.assertEqual(session['result']['financial'], {})
        self.assertFalse(session['result']['evaluation']['final_eligible'])
        self.click('app_workflow_discard')
        self.assertNotIn('offline_application_workflow', self.app.session_state)

    def test_source_read_failure_keeps_discard_and_pending_state(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        handoff = session['handoff']
        calls = session['model'].calls
        with patch('correction_workflow_ui.read_synthetic_conflict_pages',
                   side_effect=RuntimeError('sensitive parser detail')):
            self.app.run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.error)
        self.assertNotIn('sensitive parser detail', self.app.error[0].value)
        self.assertEqual(handoff['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['model'].calls, calls)
        self.assertNotIn('displayed_request_sha256', session)
        self.assertFalse(any(button.key == 'app_workflow_approve' for button in self.app.button))
        self.click('app_workflow_discard')
        self.assertNotIn('offline_application_workflow', self.app.session_state)
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')

    def test_missing_display_receipt_blocks_click_until_preview_is_shown_again(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        session.pop('displayed_request_sha256')
        calls = session['model'].calls
        self.app.button(key='app_workflow_approve').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('REQUEST_CHANGED' in item.value for item in self.app.error))
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['handoff']['checkpoint']['submission_count'], 0)
        self.assertEqual(session['model'].calls, calls)
        self.click('app_workflow_approve')
        self.assertEqual(session['handoff']['checkpoint']['submission_count'], 1)

    def test_malformed_preview_clears_previously_displayed_receipt(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        with patch('correction_workflow_ui.financial_approval_preview',
                   side_effect=ValueError('INVALID_PREVIEW')):
            self.app.run()
        self.assertFalse(self.app.exception)
        self.assertNotIn('displayed_request_sha256', session)
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['model'].calls, 2)
        self.assertFalse(any(button.key == 'app_workflow_approve' for button in self.app.button))

    def test_simultaneous_decision_clicks_do_not_approve(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        self.app.button(key='app_workflow_approve').click()
        self.app.button(key='app_workflow_reject').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('CONFLICTING_APPROVAL_DECISION' in item.value for item in self.app.error))
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['model'].calls, 2)
        self.click('app_workflow_reject')
        self.assertFalse(session['result']['evaluation']['final_eligible'])

    def test_malformed_session_can_be_discarded_without_model_dispatch(self):
        from correction_workflow_ui import SESSION_KEY
        for invalid in ([], {}, {'document_sha256': 'x', 'handoff': None},
                        {'document_sha256': 'x', 'handoff': {}, 'model': object()}):
            with self.subTest(invalid=invalid):
                self.app.session_state[SESSION_KEY] = invalid
                with patch('correction_workflow_ui.start_offline_correction_workflow') as start, \
                     patch('correction_workflow_ui.decide_and_resume_offline') as resume:
                    self.app.run()
                    self.assertFalse(self.app.exception)
                    self.assertTrue(self.app.error)
                    self.assertFalse(any(button.key == 'app_workflow_approve' for button in self.app.button))
                    self.app.button(key='app_workflow_discard').click().run()
                    self.assertFalse(self.app.exception)
                    self.assertNotIn(SESSION_KEY, self.app.session_state)
                    start.assert_not_called()
                    resume.assert_not_called()
                self.assertEqual(self.app.session_state['report'], 'Existing real analysis')
        self.click('app_workflow_start')
        self.assertEqual(self.app.session_state[SESSION_KEY]['handoff']['status'], 'AWAITING_APPROVAL')

    def test_corrupt_request_counter_blocks_decisions_and_allows_discard(self):
        from model_request_budget import ModelRequestBudget
        invalid = (
            None, {}, {'maximum': 12, 'reserved': 3, 'remaining': 10},
            {'maximum': 12, 'reserved': -1, 'remaining': 13},
            {'maximum': True, 'reserved': 0, 'remaining': 1},
        )
        for snapshot in invalid:
            with self.subTest(snapshot=snapshot):
                self.click('app_workflow_start')
                session = self.app.session_state['offline_application_workflow']
                calls = session['model'].calls
                with patch.object(ModelRequestBudget, 'snapshot', return_value=snapshot):
                    self.app.run()
                self.assertFalse(self.app.exception)
                self.assertTrue(any('request counter is invalid' in e.value
                                    for e in self.app.error))
                self.assertFalse(any(button.key in ('app_workflow_approve', 'app_workflow_reject')
                                     for button in self.app.button))
                self.assertEqual(session['model'].calls, calls)
                self.click('app_workflow_discard')
                self.assertEqual(self.app.session_state['report'], 'Existing real analysis')

    def test_request_allowance_is_visible_and_shared_across_both_approvals(self):
        self.click('app_workflow_start')
        session = self.app.session_state['offline_application_workflow']
        budget = session['model'].request_budget
        self.assertEqual(budget.snapshot(), {'maximum': 12, 'reserved': 2, 'remaining': 10})
        self.assertTrue(any('Scripted requests used: 2 of 12' in item.value for item in self.app.caption))
        self.click('app_workflow_approve')
        self.assertIs(session['model'].request_budget, budget)
        self.assertEqual(budget.snapshot()['reserved'], 5)
        self.assertTrue(any('remaining: 7' in item.value for item in self.app.caption))
        self.click('app_workflow_approve')
        self.assertEqual(budget.snapshot()['reserved'], 7)
        self.assertTrue(any('Scripted requests used: 7 of 12' in item.value for item in self.app.caption))

    def test_request_limit_practice_retains_unreviewed_progress_and_can_restart(self):
        self.app.selectbox(key='app_workflow_scenario').select('Stop at the request limit').run()
        self.click('app_workflow_start')
        self.click('app_workflow_approve')
        self.app.button(key='app_workflow_approve').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('Request allowance exhausted' in item.value for item in self.app.error))
        session = self.app.session_state['offline_application_workflow']
        self.assertEqual(session['model'].calls, 5)
        self.assertEqual(session['model'].request_budget.snapshot()['remaining'], 0)
        self.assertEqual(session['handoff']['status'], 'FAILED')
        progress = session['handoff']['failure_checkpoint']
        self.assertEqual(progress['financial_data']['revenue_current'], 120)
        self.assertIsNone(progress['review_status'])
        self.assertNotIn('result', session)
        self.assertFalse(any(button.key == 'app_workflow_approve' for button in self.app.button))
        self.assertEqual(len(self.app.get('download_button')), 0)
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')
        self.app.selectbox(key='app_workflow_scenario').select('Standard correction').run()
        self.click('app_workflow_start')
        fresh = self.app.session_state['offline_application_workflow']
        self.assertIsNot(fresh['model'], session['model'])
        self.assertEqual(fresh['model'].request_budget.snapshot()['reserved'], 2)
        self.assertEqual(fresh['model'].request_budget.snapshot()['maximum'], 12)
