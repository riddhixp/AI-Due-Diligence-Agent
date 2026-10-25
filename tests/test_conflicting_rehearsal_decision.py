import unittest
from unittest.mock import patch
from financial_approval_resume import decide_and_resume_offline
from scripted_offline_model import ScriptedOfflineModel


class ConflictingRehearsalDecisionTests(unittest.TestCase):
    def test_conflict_stops_before_any_document_or_sdk_mutation(self):
        handoff = {'status': 'AWAITING_APPROVAL'}
        model = ScriptedOfflineModel()
        responses = list(model.responses)
        with patch('financial_approval_resume.prepare_tool_state') as prepare, \
             patch('financial_approval_resume.decide_live_financial_pause') as decide:
            with self.assertRaisesRegex(ValueError, 'CONFLICTING_APPROVAL_DECISION'):
                decide_and_resume_offline(handoff, b'', True, model, stop_after_rejection=True)
        prepare.assert_not_called()
        decide.assert_not_called()
        self.assertEqual(handoff, {'status': 'AWAITING_APPROVAL'})
        self.assertEqual(model.responses, responses)
        self.assertEqual(model.calls, 0)
