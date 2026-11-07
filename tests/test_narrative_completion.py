"""Preserve specific narrative conflicts while blocking completed reports."""
import unittest
from completion_boundary import enforce_completion_boundary
from final_artifact_policy import final_report_eligible


class NarrativeCompletionTests(unittest.TestCase):
    def test_numeric_pass_cannot_override_recorded_narrative_conflict(self):
        evaluation = dict(evaluation='NEEDS_HUMAN_REVIEW',
                          financial_evidence='PRELIMINARY_CHECKS_PASSED',
                          sequence_ok=True, issues=['REVENUE_NARRATIVE_CHRONOLOGY_CONFLICT'],
                          narrative_issues=['Revenue 120 → 100 reverses chronology.'],
                          final_eligible=False)
        result = enforce_completion_boundary('Conflicting narrative',
            {'revenue_current': 120, 'revenue_previous': 100}, 1,
            {'reviewed_count': 1, 'status': 'PRELIMINARY_CHECKS_PASSED'}, evaluation)
        self.assertFalse(result['final_eligible'])
        self.assertIn('Narrative requires review', result['report'])
        self.assertIn('120 → 100', result['report'])
        self.assertNotIn('Conflicting narrative', result['report'])
        self.assertFalse(final_report_eligible(evaluation))
