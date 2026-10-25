"""Genuine SDK approval controls, using only scripted startup and blocked network."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from scripts.create_conflict_test_fixture import create_conflict_fixture


class LiveFinancialApprovalUITests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = create_conflict_fixture(Path(folder.name) / 'fixture.pdf')
        self.pdf = self.path.read_bytes()
        network = patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        network.start()
        self.addCleanup(network.stop)
        self.app = AppTest.from_string(f'''
import streamlit as st
from pathlib import Path
from offline_correction_workflow import start_offline_correction_workflow
from live_financial_approval_ui import render_live_financial_decision
pdf = Path({str(self.path)!r}).read_bytes()
if 'fixture' not in st.session_state:
    st.session_state['fixture'] = start_offline_correction_workflow(pdf)
st.session_state.setdefault('report', 'Existing real analysis')
render_live_financial_decision(st, st.session_state['fixture']['handoff'], pdf)
''', default_timeout=20).run()
        self.assertFalse(self.app.exception)

    def test_figures_and_source_evidence_are_visible_without_continuation(self):
        frame = self.app.dataframe[0].value
        self.assertEqual(frame[frame['Metric'] == 'Revenue current'].iloc[0]['Proposed'], 130)
        self.assertIn('Total revenue 120 100 90', ' '.join(item.value for item in self.app.text))
        session = self.app.session_state['fixture']
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['model'].calls, 2)
        self.assertTrue(any('Proposed figures need review' in item.value for item in self.app.warning))
        self.assertTrue(any('status' in frame.value.columns for frame in self.app.dataframe[1:]))
        self.assertEqual(session['handoff']['checkpoint']['submission_count'], 0)

    def test_approval_records_decision_without_model_or_report_changes(self):
        self.app.button(key='live_financial_approve').click().run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.error)
        session = self.app.session_state['fixture']
        self.assertEqual(session['handoff']['status'], 'APPROVED')
        self.assertEqual(session['model'].calls, 2)
        self.assertEqual(session['handoff']['checkpoint']['submission_count'], 0)
        from live_continuation_preflight import preflight_live_continuation
        readiness = preflight_live_continuation(session['handoff'], self.pdf)
        self.assertTrue(readiness['approved_request_unchanged'])
        self.assertFalse(readiness['ready_for_paid_resume'])
        self.assertFalse(readiness['model_resumed'])
        self.assertEqual(session['model'].calls, 2)
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')
        self.assertEqual(len(self.app.get('download_button')), 0)
        self.assertFalse(self.app.button)

    def test_rejection_records_decision_without_model_continuation(self):
        self.app.button(key='live_financial_reject').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state['fixture']['handoff']['status'], 'REJECTED')
        self.assertEqual(self.app.session_state['fixture']['model'].calls, 2)

    def test_replaced_request_requires_reviewing_refreshed_preview(self):
        from offline_correction_workflow import start_offline_correction_workflow
        from synthetic_financial_fixture import conflict_submission_arguments
        fields = conflict_submission_arguments(currency='GBP')
        with patch('offline_correction_workflow.conflict_submission_arguments', return_value=fields):
            replacement = start_offline_correction_workflow(self.pdf)
        session = self.app.session_state['fixture']
        session.update(replacement)
        self.app.button(key='live_financial_approve').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('REQUEST_CHANGED' in item.value for item in self.app.error))
        self.assertEqual(session['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(session['model'].calls, 2)
        self.app.button(key='live_financial_approve').click().run()
        self.assertFalse(self.app.error)
        self.assertEqual(session['handoff']['status'], 'APPROVED')
        self.assertEqual(session['model'].calls, 2)

    def test_changed_pdf_hides_decision_controls(self):
        self.path.write_bytes(self.pdf + b'changed')
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('DOCUMENT_MISMATCH' in item.value for item in self.app.error))
        self.assertFalse(self.app.button)
        self.assertEqual(self.app.session_state['fixture']['model'].calls, 2)

    def test_supported_proposal_shows_local_checks_without_accepting_figures(self):
        from financial_approval_resume import decide_and_resume_offline
        fixture = self.app.session_state['fixture']
        result = decide_and_resume_offline(fixture['handoff'], self.pdf, True, fixture['model'])
        fixture['handoff'] = result['handoff']
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('passed local preliminary checks' in item.value for item in self.app.info))
        handoff = fixture['handoff']
        self.assertEqual(handoff['status'], 'AWAITING_APPROVAL')
        self.assertEqual(handoff['checkpoint']['submission_count'], 1)
        self.assertEqual(handoff['checkpoint']['financial_data']['revenue_current'], 130)
        self.assertEqual(fixture['model'].calls, 5)
        self.assertEqual(self.app.session_state['report'], 'Existing real analysis')

    def test_unexpected_pdf_error_hides_buttons_and_invalidates_preview(self):
        from live_financial_approval_ui import DISPLAY_KEY
        fixture = self.app.session_state['fixture']
        with patch('live_financial_approval_ui.PdfReader',
                   side_effect=RuntimeError('sensitive parser detail')):
            self.app.run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.error)
        self.assertNotIn('sensitive parser detail', self.app.error[0].value)
        self.assertFalse(self.app.button)
        self.assertNotIn(DISPLAY_KEY, self.app.session_state)
        self.assertEqual(fixture['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(fixture['model'].calls, 2)
        self.app.run()
        self.assertFalse(self.app.error)
        self.assertTrue(self.app.button)
        self.assertEqual(fixture['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(fixture['model'].calls, 2)

    def test_conflicting_clicks_leave_real_pause_undecided(self):
        self.app.button(key='live_financial_approve').click()
        self.app.button(key='live_financial_reject').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('CONFLICTING_APPROVAL_DECISION' in item.value for item in self.app.error))
        fixture = self.app.session_state['fixture']
        self.assertEqual(fixture['handoff']['status'], 'AWAITING_APPROVAL')
        self.assertEqual(fixture['model'].calls, 2)
        self.app.button(key='live_financial_reject').click().run()
        self.assertFalse(self.app.error)
        self.assertEqual(fixture['handoff']['status'], 'REJECTED')
