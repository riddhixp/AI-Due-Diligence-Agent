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
        from unittest.mock import MagicMock
        for decision in ('app_workflow_approve', 'app_workflow_reject'):
            with self.subTest(decision=decision):
                st = MagicMock()
                st.session_state = {SESSION_KEY: {
                    'document_sha256': 'document-a',
                    'handoff': {'status': 'AWAITING_APPROVAL',
                                'checkpoint': {'submission_count': 0}, 'sdk_state': object()},
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
                st.error.assert_any_call('Offline approval could not continue. Check the current request or restart the rehearsal.')
                st.download_button.assert_not_called()

    def test_verified_approval_decision_resumes_scripted_workflow(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        handoff = {'status': 'AWAITING_APPROVAL', 'checkpoint': {'submission_count': 0}, 'sdk_state': object()}
        model = object()
        session = {'document_sha256': 'document-a', 'handoff': handoff,
                   'model': model, 'displayed_request_sha256': 'request-a'}
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        yes, no = MagicMock(), MagicMock()
        yes.button.return_value = True
        no.button.return_value = False
        st.columns.return_value = (yes, no)
        preview = {'metadata': {}, 'metrics': [], 'request_sha256': 'request-a'}
        result = {'status': 'COMPLETED', 'financial': {'revenue_current': 120},
                  'evaluation': {'final_eligible': False}}
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.financial_approval_preview', return_value=preview), \
             patch('correction_workflow_ui.read_synthetic_conflict_pages',
                   return_value=['page one', 'page two']), \
             patch('correction_workflow_ui.render_proposed_financial_review'), \
             patch('correction_workflow_ui.decide_and_resume_offline',
                   return_value=result) as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        resume.assert_called_once_with(handoff, b'%PDF-synthetic', True, model,
                                       expected_request_sha256='request-a',
                                       stop_after_rejection=False)
        self.assertIs(session['result'], result)
        st.rerun.assert_called_once()
        st.download_button.assert_not_called()

    def test_verified_rejection_ends_free_workflow_without_export(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        handoff = {'status': 'AWAITING_APPROVAL', 'checkpoint': {'submission_count': 0}, 'sdk_state': object()}
        model = object()
        session = {'document_sha256': 'document-a', 'handoff': handoff,
                   'model': model, 'displayed_request_sha256': 'request-a'}
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        yes, no = MagicMock(), MagicMock()
        yes.button.return_value = False
        no.button.return_value = True
        st.columns.return_value = (yes, no)
        preview = {'metadata': {}, 'metrics': [], 'request_sha256': 'request-a'}
        result = {'status': 'COMPLETED', 'financial': {'revenue_current': 130},
                  'evaluation': {'final_eligible': False}}
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.financial_approval_preview', return_value=preview), \
             patch('correction_workflow_ui.read_synthetic_conflict_pages',
                   return_value=['page one', 'page two']), \
             patch('correction_workflow_ui.render_proposed_financial_review'), \
             patch('correction_workflow_ui.decide_and_resume_offline',
                   return_value=result) as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        resume.assert_called_once_with(handoff, b'%PDF-synthetic', False, model,
                                       expected_request_sha256='request-a',
                                       stop_after_rejection=True)
        self.assertIs(session['result'], result)
        st.rerun.assert_called_once()
        st.download_button.assert_not_called()

    def test_first_approval_preserves_next_pending_correction(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        handoff = {'status': 'AWAITING_APPROVAL',
                   'checkpoint': {'submission_count': 0}, 'sdk_state': object()}
        next_handoff = {'status': 'AWAITING_APPROVAL',
                        'checkpoint': {'submission_count': 1}, 'sdk_state': object()}
        model = object()
        session = {'document_sha256': 'document-a', 'handoff': handoff,
                   'model': model, 'displayed_request_sha256': 'request-a'}
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        yes, no = MagicMock(), MagicMock()
        yes.button.return_value = True
        no.button.return_value = False
        st.columns.return_value = (yes, no)
        preview = {'metadata': {}, 'metrics': [], 'request_sha256': 'request-a'}
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.financial_approval_preview', return_value=preview), \
             patch('correction_workflow_ui.read_synthetic_conflict_pages',
                   return_value=['page one', 'page two']), \
             patch('correction_workflow_ui.render_proposed_financial_review'), \
             patch('correction_workflow_ui.decide_and_resume_offline',
                   return_value={'status': 'AWAITING_APPROVAL',
                                 'handoff': next_handoff}) as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        resume.assert_called_once()
        self.assertIs(session['handoff'], next_handoff)
        self.assertNotIn('displayed_request_sha256', session)
        self.assertNotIn('result', session)
        st.rerun.assert_called_once()
        st.download_button.assert_not_called()

    def test_completed_correction_is_simulated_and_cannot_export(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        session = {
            'document_sha256': 'document-a',
            'handoff': {'status': 'COMPLETED'},
            'model': object(),
            'result': {
                'financial': {'revenue_current': 120},
                'evaluation': {
                    'final_eligible': True,
                    'financial_evidence': 'PRELIMINARY_CHECKS_PASSED',
                },
            },
        }
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'):
            render_correction_workflow(st, b'%PDF-synthetic')
        st.success.assert_called()
        st.write.assert_any_call('Final synthetic revenue:', 120)
        st.caption.assert_any_call('This scripted result is not a final due diligence report.')
        st.download_button.assert_not_called()

    def test_rejected_correction_stays_incomplete_and_nonexportable(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        session = {
            'document_sha256': 'document-a',
            'handoff': {'status': 'COMPLETED'},
            'model': object(),
            'result': {
                'financial': {'revenue_current': 130},
                'evaluation': {
                    'final_eligible': False,
                    'financial_evidence': 'NEEDS_REVIEW',
                },
            },
        }
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'):
            render_correction_workflow(st, b'%PDF-synthetic')
        st.warning.assert_called()
        st.write.assert_any_call('Final synthetic revenue:', 130)
        st.write.assert_any_call('Completion checks passed:', False)
        st.download_button.assert_not_called()

    def test_request_limit_failure_shows_read_only_progress_without_export(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        session = {
            'document_sha256': 'document-a',
            'request_limit_practice': True,
            'handoff': {
                'status': 'FAILED',
                'failure_checkpoint': {
                    'submission_count': 2,
                    'review_status': None,
                    'financial_data': {'revenue_current': 120},
                },
            },
            'model': object(),
            'workflow_error': 'Request allowance exhausted. Progress is retained.',
        }
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Stop at the request limit'
        st.button.return_value = False
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        st.write.assert_any_call('Accepted submissions before failure:', 2)
        st.write.assert_any_call('Latest review status:', 'Not completed')
        st.write.assert_any_call('Last accepted synthetic revenue:', 120)
        resume.assert_not_called()
        st.download_button.assert_not_called()

    def test_discard_failed_rehearsal_preserves_unrelated_analysis(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        st.session_state = {
            SESSION_KEY: {
                'document_sha256': 'document-a',
                'handoff': {'status': 'FAILED'},
                'model': object(),
                'workflow_error': 'Request allowance exhausted.',
            },
            'report': 'Previously reviewed analysis',
        }
        st.selectbox.return_value = 'Standard correction'
        st.button.side_effect = lambda *args, **kwargs: (
            kwargs.get('key') == 'app_workflow_discard')
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        self.assertNotIn(SESSION_KEY, st.session_state)
        self.assertEqual(st.session_state['report'], 'Previously reviewed analysis')
        resume.assert_not_called()
        st.rerun.assert_called_once()
        st.download_button.assert_not_called()

    def test_invalid_failure_checkpoint_does_not_resume_or_export(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        st.session_state = {
            SESSION_KEY: {
                'document_sha256': 'document-a',
                'handoff': {
                    'status': 'FAILED',
                    'failure_checkpoint': {
                        'submission_count': -1,
                        'review_status': None,
                        'financial_data': {'revenue_current': 120},
                    },
                },
                'model': object(),
            }
        }
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        st.warning.assert_called()
        resume.assert_not_called()
        st.download_button.assert_not_called()
        self.assertTrue(any(call.kwargs.get('key') == 'app_workflow_discard'
                            for call in st.button.call_args_list))

    def test_invalid_completed_result_stays_nonexportable(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        st.session_state = {SESSION_KEY: {
            'document_sha256': 'document-a',
            'handoff': {'status': 'COMPLETED'},
            'model': object(),
            'result': {'financial': {'revenue_current': 120},
                       'evaluation': {'final_eligible': 'yes',
                                      'financial_evidence': 'PASS'}},
        }}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        st.error.assert_called()
        resume.assert_not_called()
        st.download_button.assert_not_called()
        self.assertTrue(any(c.kwargs.get('key') == 'app_workflow_discard'
                            for c in st.button.call_args_list))

    def test_missing_completed_evidence_cannot_claim_success(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        st.session_state = {SESSION_KEY: {
            'document_sha256': 'document-a',
            'handoff': {'status': 'COMPLETED'},
            'model': object(),
            'result': {'financial': {'revenue_current': 120},
                       'evaluation': {'final_eligible': True,
                                      'financial_evidence': ''}},
        }}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        st.error.assert_called()
        resume.assert_not_called()
        st.download_button.assert_not_called()

    def test_invalid_saved_session_blocks_start_button(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        st.session_state = {SESSION_KEY: {'document_sha256': 'document-a'}}
        st.button.side_effect = lambda *args, **kwargs: (
            kwargs.get('key') == 'app_workflow_start')
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.start_offline_correction_workflow') as start, \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        start.assert_not_called()
        resume.assert_not_called()
        st.error.assert_called()
        st.download_button.assert_not_called()

    def test_failed_workflow_does_not_offer_approval_controls(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        st.session_state = {SESSION_KEY: {
            'document_sha256': 'document-a',
            'handoff': {'status': 'FAILED'},
            'model': object(),
            'workflow_error': 'Scripted request allowance exhausted.',
        }}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        resume.assert_not_called()
        self.assertFalse(any(c.kwargs.get('key') in (
            'app_workflow_approve', 'app_workflow_reject')
            for c in st.button.call_args_list))
        st.download_button.assert_not_called()

    def test_document_change_clears_pending_approval_fingerprint(self):
        self.st.session_state[SESSION_KEY] = {
            'document_sha256': 'document-old',
            'handoff': {'status': 'AWAITING_APPROVAL'},
            'model': object(),
            'displayed_request_sha256': 'old-request',
        }
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-new'), \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume, \
             patch('correction_workflow_ui.start_offline_correction_workflow') as start:
            render_correction_workflow(self.st, b'%PDF-new')
        self.assertNotIn(SESSION_KEY, self.st.session_state)
        resume.assert_not_called()
        start.assert_not_called()
        self.st.download_button.assert_not_called()

    def test_changed_document_allows_fresh_free_rehearsal_only(self):
        old = {'document_sha256': 'old-document',
               'handoff': {'status': 'AWAITING_APPROVAL'},
               'model': object(), 'displayed_request_sha256': 'old-request'}
        fresh = {'handoff': {'status': 'FAILED'}, 'model': object(),
                 'scenario': 'standard'}
        self.st.session_state[SESSION_KEY] = old
        self.st.button.side_effect = lambda *args, **kwargs: (
            kwargs.get('key') == 'app_workflow_start')
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='new-document'), \
             patch('correction_workflow_ui.start_offline_correction_workflow',
                   return_value=fresh) as start, \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume:
            render_correction_workflow(self.st, b'%PDF-new')
        start.assert_called_once_with(b'%PDF-new', scenario='standard', request_limit=12)
        resume.assert_not_called()
        self.assertIs(self.st.session_state[SESSION_KEY], fresh)
        self.assertEqual(fresh['document_sha256'], 'new-document')
        self.assertNotIn('displayed_request_sha256', fresh)
        self.st.download_button.assert_not_called()

    def test_restarting_same_document_resets_old_approval_request(self):
        previous = {'document_sha256': 'document-a',
                    'handoff': {'status': 'FAILED'},
                    'model': object(),
                    'displayed_request_sha256': 'previous-request'}
        fresh = {'handoff': {'status': 'FAILED'}, 'model': object(),
                 'scenario': 'standard'}
        self.st.session_state[SESSION_KEY] = previous
        self.st.button.side_effect = lambda *args, **kwargs: (
            kwargs.get('key') == 'app_workflow_start')
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.start_offline_correction_workflow',
                   return_value=fresh) as start, \
             patch('correction_workflow_ui.decide_and_resume_offline') as resume:
            render_correction_workflow(self.st, b'%PDF-synthetic')
        start.assert_called_once_with(b'%PDF-synthetic', scenario='standard', request_limit=12)
        resume.assert_not_called()
        self.assertIs(self.st.session_state[SESSION_KEY], fresh)
        self.assertNotIn('displayed_request_sha256', fresh)
        self.st.download_button.assert_not_called()

    def test_start_failure_does_not_replace_existing_rehearsal(self):
        previous = {'document_sha256': 'document-a',
                    'handoff': {'status': 'FAILED'},
                    'model': object()}
        self.st.session_state[SESSION_KEY] = previous
        self.st.button.side_effect = lambda *args, **kwargs: (
            kwargs.get('key') == 'app_workflow_start')
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.start_offline_correction_workflow',
                   side_effect=ValueError('SYNTHETIC_CONFLICT_PDF_REQUIRED')) as start:
            render_correction_workflow(self.st, b'%PDF-invalid')
        start.assert_called_once()
        self.assertIs(self.st.session_state[SESSION_KEY], previous)
        self.st.error.assert_any_call('Free rehearsal could not start. Check the synthetic PDF and try again.')
        self.st.download_button.assert_not_called()

    def test_failed_approval_continuation_cannot_create_completed_result(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        handoff = {'status': 'AWAITING_APPROVAL',
                   'checkpoint': {'submission_count': 0}, 'sdk_state': object()}
        session = {'document_sha256': 'document-a', 'handoff': handoff,
                   'model': object(), 'displayed_request_sha256': 'request-a'}
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        yes, no = MagicMock(), MagicMock()
        yes.button.return_value = True
        no.button.return_value = False
        st.columns.return_value = (yes, no)
        preview = {'metadata': {}, 'metrics': [], 'request_sha256': 'request-a'}
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.financial_approval_preview',
                   return_value=preview), \
             patch('correction_workflow_ui.read_synthetic_conflict_pages',
                   return_value=['page one', 'page two']), \
             patch('correction_workflow_ui.render_proposed_financial_review'), \
             patch('correction_workflow_ui.decide_and_resume_offline',
                   side_effect=ValueError('APPROVAL_RESUME_ALREADY_CLAIMED')) as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        resume.assert_called_once()
        self.assertNotIn('result', session)
        st.error.assert_any_call('Offline approval could not continue. Check the current request or restart the rehearsal.')
        st.download_button.assert_not_called()

    def test_unexpected_continuation_error_does_not_create_result(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        handoff = {'status': 'AWAITING_APPROVAL',
                   'checkpoint': {'submission_count': 0}, 'sdk_state': object()}
        session = {'document_sha256': 'document-a', 'handoff': handoff,
                   'model': object(), 'displayed_request_sha256': 'request-a'}
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        yes, no = MagicMock(), MagicMock()
        yes.button.return_value = True
        no.button.return_value = False
        st.columns.return_value = (yes, no)
        preview = {'metadata': {}, 'metrics': [], 'request_sha256': 'request-a'}
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.financial_approval_preview',
                   return_value=preview), \
             patch('correction_workflow_ui.read_synthetic_conflict_pages',
                   return_value=['page one', 'page two']), \
             patch('correction_workflow_ui.render_proposed_financial_review'), \
             patch('correction_workflow_ui.decide_and_resume_offline',
                   side_effect=RuntimeError('private internal error')) as resume:
            render_correction_workflow(st, b'%PDF-synthetic')
        resume.assert_called_once()
        self.assertNotIn('result', session)
        st.error.assert_any_call('Offline continuation could not start. No automatic retry was made.')
        self.assertFalse(any('private internal error' in str(call)
                             for call in st.error.call_args_list))
        st.download_button.assert_not_called()

    def test_start_error_never_leaks_private_exception_text(self):
        self.st.button.side_effect = lambda *args, **kwargs: (
            kwargs.get('key') == 'app_workflow_start')
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.start_offline_correction_workflow',
                   side_effect=ValueError('private client document text')):
            render_correction_workflow(self.st, b'%PDF-invalid')
        self.assertNotIn(SESSION_KEY, self.st.session_state)
        self.st.error.assert_any_call(
            'Free rehearsal could not start. Check the synthetic PDF and try again.')
        self.assertNotIn('private client document text',
                         str(self.st.error.call_args_list))

    def test_invalid_approval_preview_does_not_leak_internal_details(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        st.session_state = {SESSION_KEY: {
            'document_sha256': 'document-a',
            'handoff': {'status': 'AWAITING_APPROVAL'},
            'model': object(),
            'displayed_request_sha256': 'old-request',
        }}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        with patch('correction_workflow_ui.document_fingerprint',
                   return_value='document-a'), \
             patch('correction_workflow_ui.financial_approval_preview',
                   side_effect=ValueError('private financial details')) as preview:
            render_correction_workflow(st, b'%PDF-synthetic')
        preview.assert_called_once()
        self.assertNotIn('displayed_request_sha256', st.session_state[SESSION_KEY])
        st.error.assert_any_call(
            'Financial approval preview is invalid. Discard and restart the free rehearsal.')
        self.assertNotIn('private financial details', str(st.error.call_args_list))
        st.download_button.assert_not_called()

    def test_failed_resume_does_not_restore_old_approval_fingerprint(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        handoff = {'status': 'AWAITING_APPROVAL',
                   'checkpoint': {'submission_count': 0}, 'sdk_state': object()}
        session = {'document_sha256': 'document-a', 'handoff': handoff,
                   'model': object(), 'displayed_request_sha256': 'request-a'}
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        yes, no = MagicMock(), MagicMock()
        yes.button.return_value = True
        no.button.return_value = False
        st.columns.return_value = (yes, no)
        preview = {'metadata': {}, 'metrics': [], 'request_sha256': 'request-a'}
        def fail_resume(*args, **kwargs):
            handoff['status'] = 'FAILED'
            session.pop('displayed_request_sha256', None)
            raise ValueError('MODEL_REQUEST_BUDGET_EXHAUSTED')
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.financial_approval_preview', return_value=preview), \
             patch('correction_workflow_ui.read_synthetic_conflict_pages',
                   return_value=['page one', 'page two']), \
             patch('correction_workflow_ui.render_proposed_financial_review'), \
             patch('correction_workflow_ui.decide_and_resume_offline',
                   side_effect=fail_resume):
            render_correction_workflow(st, b'%PDF-synthetic')
        self.assertEqual(handoff['status'], 'FAILED')
        self.assertNotIn('displayed_request_sha256', session)
        self.assertIn('allowance exhausted', session['workflow_error'])
        st.rerun.assert_called_once()
        st.download_button.assert_not_called()

    def test_unexpected_failure_after_handoff_does_not_restore_approval(self):
        from unittest.mock import MagicMock
        st = MagicMock()
        handoff = {'status': 'AWAITING_APPROVAL',
                   'checkpoint': {'submission_count': 0}, 'sdk_state': object()}
        session = {'document_sha256': 'document-a', 'handoff': handoff,
                   'model': object(), 'displayed_request_sha256': 'request-a'}
        st.session_state = {SESSION_KEY: session}
        st.selectbox.return_value = 'Standard correction'
        st.button.return_value = False
        yes, no = MagicMock(), MagicMock()
        yes.button.return_value = True
        no.button.return_value = False
        st.columns.return_value = (yes, no)
        preview = {'metadata': {}, 'metrics': [], 'request_sha256': 'request-a'}
        def fail_resume(*args, **kwargs):
            handoff['status'] = 'FAILED'
            session.pop('displayed_request_sha256', None)
            raise RuntimeError('internal details')
        with patch('correction_workflow_ui.document_fingerprint', return_value='document-a'), \
             patch('correction_workflow_ui.financial_approval_preview', return_value=preview), \
             patch('correction_workflow_ui.read_synthetic_conflict_pages',
                   return_value=['page one', 'page two']), \
             patch('correction_workflow_ui.render_proposed_financial_review'), \
             patch('correction_workflow_ui.decide_and_resume_offline', side_effect=fail_resume):
            render_correction_workflow(st, b'%PDF-synthetic')
        self.assertNotIn('displayed_request_sha256', session)
        self.assertEqual(session['workflow_error'],
                         'Offline continuation failed. Start a new rehearsal to continue.')
        self.assertNotIn('internal details', str(st.error.call_args_list))
        st.rerun.assert_called_once()

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
