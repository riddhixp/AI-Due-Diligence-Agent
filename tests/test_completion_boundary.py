import unittest
from completion_boundary import enforce_completion_boundary


class CompletionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.state = {"reviewed_count": 1, "status": "PRELIMINARY_CHECKS_PASSED"}
        self.evaluation = {
            "evaluation": "PRELIMINARY_PASS",
            "financial_evidence": "PRELIMINARY_CHECKS_PASSED",
            "sequence_ok": True,
            "issues": [],
        }

    def check(self, count=1):
        return enforce_completion_boundary(
            "MODEL FINISHED REPORT", {"revenue_current": 120}, count,
            self.state, self.evaluation,
        )

    def test_success_retains_report(self):
        result = self.check()
        self.assertTrue(result["final_eligible"])
        self.assertEqual(result["report"], "MODEL FINISHED REPORT")

    def test_unreviewed_correction_blocks_completion(self):
        result = self.check(count=2)
        self.assertFalse(result["final_eligible"])
        self.assertNotIn("MODEL FINISHED REPORT", result["report"])

    def test_failed_review_blocks_completion(self):
        self.state["status"] = "NEEDS_REVIEW"
        self.assertFalse(self.check()["final_eligible"])

    def test_model_claim_cannot_override_evidence(self):
        self.evaluation["financial_evidence"] = "NEEDS_REVIEW"
        self.assertFalse(self.check()["final_eligible"])

    def test_bad_tool_sequence_blocks_completion(self):
        self.evaluation["sequence_ok"] = False
        self.assertFalse(self.check()["final_eligible"])
