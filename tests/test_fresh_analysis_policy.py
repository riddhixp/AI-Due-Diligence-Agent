import unittest
from fresh_analysis_policy import fresh_analysis_block_reason


class FreshAnalysisPolicyTests(unittest.TestCase):
    def test_no_pause_allows_fresh_analysis(self):
        self.assertIsNone(fresh_analysis_block_reason(None))

    def test_all_stored_pause_states_require_explicit_discard(self):
        for status in ['AWAITING_APPROVAL', 'APPROVED', 'REJECTED', 'FAILED', 'RESUMING_OFFLINE']:
            self.assertIn('Discard', fresh_analysis_block_reason({'status': status}))

    def test_malformed_stored_pause_does_not_unlock_analysis(self):
        for value in [{}, False, '', []]:
            self.assertIsNotNone(fresh_analysis_block_reason(value))
