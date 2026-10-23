"""Offline integration scenarios for the financial investigation workflow.

These tests exercise deterministic Python review and guardrails. They do not
simulate an LLM or demonstrate autonomous reasoning.
"""

import copy
import unittest

from agent_financial_review import review_financial_evidence
from investigation_control import submission_block_reason
from investigation_guidance import investigation_next_actions
from investigation_outcome import investigation_outcome


from synthetic_financial_fixture import PAGES, supported_submission


class InvestigationScenarioTests(unittest.TestCase):
    def test_wrong_year_to_evidence_supported_correction(self):
        submitted = supported_submission()
        submitted["revenue_current"] = 100
        submitted["reported"]["revenue_growth"] = 0.0
        initial = review_financial_evidence(PAGES, submitted)
        self.assertEqual(initial["status"], "NEEDS_REVIEW")

        actions = investigation_next_actions(initial)
        self.assertTrue(
            any("Current-year revenue" in action for action in actions)
        )

        blocked = submission_block_reason(1, 1, "NEEDS_REVIEW", 0)
        self.assertIn("SOURCE_RECHECK_REQUIRED", blocked)
        self.assertIsNone(
            submission_block_reason(1, 1, "NEEDS_REVIEW", 1)
        )

        corrected = copy.deepcopy(submitted)
        corrected["revenue_current"] = 120
        corrected["reported"]["revenue_growth"] = 20.0
        final = review_financial_evidence(PAGES, corrected)
        self.assertEqual(final["status"], "PRELIMINARY_CHECKS_PASSED")

        audit = investigation_outcome(
            2, 2, final["status"],
            ["submit_financial_data", "review_submitted_financials",
             "read_page", "submit_financial_data",
             "review_submitted_financials"],
        )
        self.assertEqual(
            audit["outcome"], "CORRECTION_PASSED_PRELIMINARY_CHECKS"
        )
        self.assertTrue(audit["latest_submission_reviewed"])

    def test_missing_metadata_remains_unresolved(self):
        submission = supported_submission()
        submission["currency"] = "unspecified"
        submission["units"] = "unspecified"

        initial = review_financial_evidence(PAGES, submission)
        self.assertEqual(initial["status"], "NEEDS_REVIEW")
        self.assertEqual(len(initial["metadata_issues"]), 2)
        self.assertTrue(
            any("unspecified" in action
                for action in investigation_next_actions(initial))
        )

        self.assertIsNone(
            submission_block_reason(1, 1, "NEEDS_REVIEW", 1)
        )
        # Re-reading an unchanged document cannot supply unknown metadata.
        second = review_financial_evidence(PAGES, submission)
        audit = investigation_outcome(
            2, 2, second["status"],
            ["read_page", "review_submitted_financials"] * 2,
        )
        self.assertEqual(
            audit["outcome"], "CORRECTION_STILL_NEEDS_REVIEW"
        )

    def test_no_second_submission_after_successful_review(self):
        submitted = supported_submission()
        first = review_financial_evidence(PAGES, submitted)
        self.assertEqual(first["status"], "PRELIMINARY_CHECKS_PASSED")
        denial = submission_block_reason(1, 1, first["status"], 3)
        self.assertIn("CORRECTION_NOT_PERMITTED", denial)

    def test_third_submission_denied_even_after_failed_review(self):
        denial = submission_block_reason(2, 2, "NEEDS_REVIEW", 10)
        self.assertIn("SUBMISSION_LIMIT_REACHED", denial)

    def test_unreviewed_correction_must_not_report_success(self):
        audit = investigation_outcome(
            2, 1, "NEEDS_REVIEW",
            ["submit_financial_data", "review_submitted_financials",
             "read_page", "submit_financial_data"],
        )
        self.assertEqual(
            audit["outcome"], "LATEST_SUBMISSION_UNREVIEWED"
        )


if __name__ == "__main__":
    unittest.main()
