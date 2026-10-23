import unittest
from final_artifact_policy import final_report_eligible


class FinalArtifactPolicyTests(unittest.TestCase):
    def setUp(self):
        self.passed = {
            "evaluation": "PRELIMINARY_PASS",
            "financial_evidence": "PRELIMINARY_CHECKS_PASSED",
            "sequence_ok": True,
            "issues": [],
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
