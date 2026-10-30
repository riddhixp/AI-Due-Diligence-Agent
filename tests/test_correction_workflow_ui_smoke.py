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
