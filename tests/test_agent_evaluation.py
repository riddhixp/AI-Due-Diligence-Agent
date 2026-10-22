import copy
import unittest

from agent_evaluation import evaluate_agent_run
from tests.test_investigation_scenarios import PAGES, supported_submission


class AgentEvaluationTests(unittest.TestCase):
    def test_correct_reviewed_submission_passes_preliminary_gate(self):
        result = evaluate_agent_run(
            PAGES, supported_submission(),
            ["read_page", "submit_financial_data", "review_submitted_financials"],
            1, 1, "PRELIMINARY_CHECKS_PASSED",
        )
        self.assertEqual(result["evaluation"], "PRELIMINARY_PASS")

    def test_correct_but_unreviewed_submission_is_not_passed(self):
        result = evaluate_agent_run(
            PAGES, supported_submission(),
            ["read_page", "submit_financial_data"],
            1, 0, None,
        )
        self.assertEqual(result["evaluation"], "NEEDS_HUMAN_REVIEW")
        self.assertIn("LATEST_SUBMISSION_NOT_REVIEWED", result["issues"])

    def test_wrong_year_and_fake_calculation_are_flagged(self):
        submission = copy.deepcopy(supported_submission())
        submission["revenue_current"] = 100
        submission["reported"]["revenue_growth"] = 0
        result = evaluate_agent_run(
            PAGES, submission,
            ["submit_financial_data", "review_submitted_financials"],
            1, 1, "NEEDS_REVIEW",
        )
        self.assertEqual(result["evaluation"], "NEEDS_HUMAN_REVIEW")
        self.assertEqual(result["financial_evidence"], "NEEDS_REVIEW")

    def test_missing_currency_is_not_success(self):
        submission = copy.deepcopy(supported_submission())
        submission["currency"] = "unspecified"
        result = evaluate_agent_run(
            PAGES, submission,
            ["submit_financial_data", "review_submitted_financials"],
            1, 1, "NEEDS_REVIEW",
        )
        self.assertIn("FINANCIAL_EVIDENCE_REQUIRES_REVIEW", result["issues"])

    def test_stale_success_status_cannot_override_failed_evidence(self):
        submission = copy.deepcopy(supported_submission())
        submission["revenue_current"] = 100
        result = evaluate_agent_run(
            PAGES, submission,
            ["submit_financial_data", "review_submitted_financials"],
            1, 1, "PRELIMINARY_CHECKS_PASSED",
        )
        self.assertEqual(result["evaluation"], "NEEDS_HUMAN_REVIEW")
        self.assertIn("REVIEW_STATUS_EVIDENCE_MISMATCH", result["issues"])

    def test_stale_failure_status_cannot_pass_valid_evidence(self):
        result = evaluate_agent_run(
            PAGES, supported_submission(),
            ["submit_financial_data", "review_submitted_financials"],
            1, 1, "NEEDS_REVIEW",
        )
        self.assertEqual(result["evaluation"], "NEEDS_HUMAN_REVIEW")
        self.assertIn("REVIEW_STATUS_EVIDENCE_MISMATCH", result["issues"])

    def test_corrected_but_unreviewed_data_is_not_passed(self):
        result = evaluate_agent_run(
            PAGES, supported_submission(),
            ["submit_financial_data", "review_submitted_financials",
             "read_page", "submit_financial_data"],
            2, 1, None,
        )
        self.assertEqual(result["evaluation"], "NEEDS_HUMAN_REVIEW")
        self.assertIn("CORRECTION_NOT_FOLLOWED_BY_REVIEW", result["issues"])


if __name__ == "__main__":
    unittest.main()
