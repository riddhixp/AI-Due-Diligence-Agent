"""Offline tests of Streamlit correction controls without launching a browser."""
import unittest
from unittest.mock import Mock, patch

from correction_workflow_ui import SESSION_KEY, render_correction_workflow


class CorrectionWorkflowUiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.st = Mock()
        self.st.session_state = {}
        self.st.selectbox.return_value = 'Standard correction'
        self.st.button.return_value = False

    def test_idle_interface_never_starts_model_or_exports_report(self):
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.start_offline_correction_workflow') as start:
            render_correction_workflow(self.st, b'%PDF-synthetic')
        self.st.subheader.assert_called_with('FREE application correction workflow')
        self.st.selectbox.assert_called_once()
        start.assert_not_called()
        self.assertNotIn(SESSION_KEY, self.st.session_state)
        self.st.download_button.assert_not_called()

    def test_malformed_stored_rehearsal_can_only_be_discarded(self):
        self.st.session_state[SESSION_KEY] = {'document_sha256': 'document-a'}
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.start_offline_correction_workflow') as start:
            render_correction_workflow(self.st, b'%PDF-synthetic')
        start.assert_not_called()
        self.st.error.assert_called()
        self.st.download_button.assert_not_called()
        self.assertTrue(any(c.kwargs.get('key') == 'app_workflow_discard'
                            for c in self.st.button.call_args_list))

    def test_discard_button_clears_stored_rehearsal(self):
        self.st.session_state[SESSION_KEY] = {'document_sha256': 'document-a'}
        self.st.button.side_effect = lambda *args, **kwargs: kwargs.get('key') == 'app_workflow_discard'
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.start_offline_correction_workflow') as start:
            render_correction_workflow(self.st, b'%PDF-synthetic')
        self.assertNotIn(SESSION_KEY, self.st.session_state)
        self.st.rerun.assert_called_once()
        start.assert_not_called()

    def test_start_button_creates_only_scripted_rehearsal(self):
        session = {'handoff': {'status': 'FAILED'}, 'model': object(),
                   'scenario': 'standard'}
        self.st.button.side_effect = lambda *args, **kwargs: kwargs.get('key') == 'app_workflow_start'
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.start_offline_correction_workflow',
                   return_value=session) as start:
            render_correction_workflow(self.st, b'%PDF-synthetic')
        start.assert_called_once_with(b'%PDF-synthetic', scenario='standard', request_limit=12)
        self.assertIs(self.st.session_state[SESSION_KEY], session)
        self.assertEqual(session['document_sha256'], 'document-a')
        self.assertFalse(session['request_limit_practice'])
        self.st.download_button.assert_not_called()

    def test_request_limit_scenario_uses_five_scripted_requests(self):
        session = {'handoff': {'status': 'FAILED'}, 'model': object(),
                   'scenario': 'standard'}
        self.st.selectbox.return_value = 'Stop at the request limit'
        self.st.button.side_effect = lambda *args, **kwargs: kwargs.get('key') == 'app_workflow_start'
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.start_offline_correction_workflow',
                   return_value=session) as start:
            render_correction_workflow(self.st, b'%PDF-synthetic')
        start.assert_called_once_with(b'%PDF-synthetic', scenario='standard', request_limit=5)
        self.assertTrue(self.st.session_state[SESSION_KEY]['request_limit_practice'])
        self.st.download_button.assert_not_called()

    def test_approve_and_reject_buttons_require_current_fingerprint(self):
        for decision in ('app_workflow_approve', 'app_workflow_reject'):
            with self.subTest(decision=decision):
                st = Mock()
                st.session_state = {SESSION_KEY: {
                    'document_sha256': 'document-a',
                    'handoff': {'status': 'AWAITING_APPROVAL',
                                'checkpoint': {'submission_count': 0}},
                    'model': object()}}
                st.selectbox.return_value = 'Standard correction'
                st.button.return_value = False
                approve = decision == 'app_workflow_approve'
                yes, no = Mock(), Mock()
                yes.button.return_value = approve
                no.button.return_value = not approve
                st.columns.return_value = (yes, no)
                preview = {'metadata': {}, 'metrics': [], 'request_sha256': 'request-a'}
                with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
                     patch('correction_workflow_ui.financial_approval_preview', return_value=preview), \
                     patch('correction_workflow_ui.read_synthetic_conflict_pages',
                           return_value=['page one', 'page two']), \
                     patch('correction_workflow_ui.render_proposed_financial_review'), \
                     patch('correction_workflow_ui.decide_and_resume_offline') as resume:
                    render_correction_workflow(st, b'%PDF-synthetic')
                resume.assert_not_called()
                st.error.assert_any_call('FINANCIAL_APPROVAL_REQUEST_CHANGED')
                st.download_button.assert_not_called()

    def test_different_document_clears_stale_rehearsal(self):
        self.st.session_state[SESSION_KEY] = {
            'document_sha256': 'document-old',
            'handoff': {'status': 'AWAITING_APPROVAL'},
            'model': object(),
        }
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-new'), \
             patch('correction_workflow_ui.start_offline_correction_workflow') as start:
            render_correction_workflow(self.st, b'%PDF-synthetic')
        self.assertNotIn(SESSION_KEY, self.st.session_state)
        start.assert_not_called()
        self.st.download_button.assert_not_called()


if __name__ == '__main__':
    unittest.main()
