import unittest
from document_session import DOCUMENT_STATE_KEYS, set_active_document


class DocumentSessionTests(unittest.TestCase):
    def setUp(self):
        self.identity = ('report.pdf', 100, 'a' * 64)
        self.state = {key: object() for key in DOCUMENT_STATE_KEYS}
        self.state.update(file_id=self.identity, smoke_test_mode=True, preferred_theme='dark')

    def test_same_document_preserves_pending_state(self):
        previous = dict(self.state)
        self.assertFalse(set_active_document(self.state, self.identity))
        self.assertEqual(self.state, previous)

    def test_same_filename_and_size_with_different_content_clears_state(self):
        changed = ('report.pdf', 100, 'b' * 64)
        self.assertTrue(set_active_document(self.state, changed))
        self.assertEqual(self.state, {'file_id': changed, 'smoke_test_mode': True, 'preferred_theme': 'dark'})

    def test_removal_clears_all_document_state_but_keeps_preferences(self):
        self.assertTrue(set_active_document(self.state, None))
        self.assertEqual(self.state, {'smoke_test_mode': True, 'preferred_theme': 'dark'})
        self.assertFalse(set_active_document(self.state, None))

    def test_orphaned_state_is_cleared_even_without_document_identity(self):
        self.state.pop('file_id')
        self.assertTrue(set_active_document(self.state, None))
        self.assertNotIn('live_financial_pause', self.state)
        self.assertNotIn('report', self.state)
