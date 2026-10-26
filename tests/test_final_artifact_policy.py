import unittest
from final_artifact_policy import final_report_eligible


class FinalArtifactPolicyTests(unittest.TestCase):
    def setUp(self):
        self.passed = {
            "evaluation": "PRELIMINARY_PASS",
            "financial_evidence": "PRELIMINARY_CHECKS_PASSED",
            "sequence_ok": True,
            "issues": [],
            "final_eligible": True,
            "final_response_complete": True,
            "simulation": False,
        }

    def test_preliminary_pass(self):
        self.assertTrue(final_report_eligible(self.passed))

    def test_missing_evaluation_is_not_final(self):
        self.assertFalse(final_report_eligible(None))

    def test_interruption_not_final(self):
        self.passed["evaluation"] = "INTERRUPTED_TURN_LIMIT"
        self.assertFalse(final_report_eligible(self.passed))

    def test_simulation_not_final(self):
        self.passed["simulation"] = True
        self.assertFalse(final_report_eligible(self.passed))

    def test_unreviewed_evidence_not_final(self):
        self.passed["financial_evidence"] = "NEEDS_REVIEW"
        self.assertFalse(final_report_eligible(self.passed))

    def test_explicit_not_final(self):
        self.passed["final_eligible"] = False
        self.assertFalse(final_report_eligible(self.passed))

    def test_sequence_issues_not_final(self):
        self.passed["issues"] = ["LATEST_SUBMISSION_NOT_REVIEWED"]
        self.assertFalse(final_report_eligible(self.passed))

    def test_positive_review_cannot_override_incomplete_continuation(self):
        # Financial evidence may pass before a final model response is produced.
        # Export must still fail for an interrupted or pending SDK handoff.
        for status in ("FAILED", "AWAITING_APPROVAL", "RESUMING_OFFLINE"):
            with self.subTest(status=status):
                handoff = {"status": status, "live_resume_enabled": False}
                self.assertFalse(final_report_eligible(self.passed, handoff))

    def test_missing_final_response_cannot_export_after_passed_review(self):
        self.passed["final_response_complete"] = False
        self.assertFalse(final_report_eligible(self.passed))

    def test_completion_must_be_explicit_boolean_true(self):
        for value in [None, 1, 'true', {}, []]:
            with self.subTest(value=value):
                self.passed['final_eligible'] = value
                self.assertFalse(final_report_eligible(self.passed))
        self.passed.pop('final_eligible')
        self.assertFalse(final_report_eligible(self.passed))

    def test_simulation_mode_must_be_explicit_boolean_false(self):
        for value in [None, 0, 'false', {}, []]:
            with self.subTest(value=value):
                self.passed['simulation'] = value
                self.assertFalse(final_report_eligible(self.passed))
        self.passed.pop('simulation')
        self.assertFalse(final_report_eligible(self.passed))
