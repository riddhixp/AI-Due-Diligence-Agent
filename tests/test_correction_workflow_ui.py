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
