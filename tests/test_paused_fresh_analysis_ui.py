"""Drive the real app with an uploaded fixture; never permit a provider run."""
from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from scripts.create_conflict_test_fixture import create_conflict_fixture
from offline_correction_workflow import start_offline_correction_workflow
from investigation_checkpoint import document_fingerprint


class PausedFreshAnalysisUITests(unittest.TestCase):
    def test_pause_blocks_analysis_until_discard_without_model_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            fixture = start_offline_correction_workflow(pdf)
            upload = BytesIO(pdf)
            upload.name = 'fixture.pdf'
            app_path = Path(__file__).resolve().parents[1] / 'app.py'
            app = AppTest.from_file(str(app_path), default_timeout=20)
            app.session_state['file_id'] = (upload.name, len(pdf), document_fingerprint(pdf))
            app.session_state['live_financial_pause'] = fixture['handoff']
            with patch('streamlit.file_uploader', return_value=upload), \
                 patch('report_storage.load_report', return_value=None), \
                 patch('due_diligence_engine.run_due_diligence', side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as run:
                app.run()
                self.assertFalse(app.exception)
                self.assertTrue(app.button(key='analyse_company').disabled)
                # Simulate a dispatched event despite the disabled UI to exercise
                # the independent server-side check before provider/key lookup.
                import streamlit as st
                button = st.button
                def dispatched(*args, **kwargs):
                    result = button(*args, **kwargs)
                    return True if kwargs.get('key') == 'analyse_company' else result
                with patch('streamlit.button', side_effect=dispatched):
                    app.run()
                self.assertFalse(app.exception)
                self.assertTrue(any('Discard the paused investigation' in item.value for item in app.error))
                run.assert_not_called()
                self.assertEqual(fixture['model'].calls, 2)
                app.button(key='live_financial_approve').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(fixture['handoff']['status'], 'APPROVED')
                self.assertTrue(app.button(key='analyse_company').disabled)
                self.assertEqual(fixture['model'].calls, 2)
                discard = next(button for button in app.button if button.label == 'Discard paused investigation')
                discard.click().run()
                self.assertFalse(app.exception)
                self.assertNotIn('live_financial_pause', app.session_state)
                self.assertFalse(app.button(key='analyse_company').disabled)
                run.assert_not_called()
