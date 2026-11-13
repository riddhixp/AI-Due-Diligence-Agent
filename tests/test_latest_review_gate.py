import unittest
from unittest.mock import patch
from latest_review_gate import trusted_latest_review


class LatestReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.financial = {"revenue_current": 120}
        self.state = {"reviewed_count": 1, "status": "PRELIMINARY_CHECKS_PASSED"}

    @patch("latest_review_gate.review_financial_evidence", return_value={"status": "PRELIMINARY_CHECKS_PASSED"})
    def test_matching_latest_review_permitted(self, review):
        self.assertEqual(trusted_latest_review(["page"], self.financial, 1, self.state)["status"], "PRELIMINARY_CHECKS_PASSED")
        review.assert_called_once()

    @patch("latest_review_gate.review_financial_evidence")
    def test_unreviewed_submission_cannot_get_pass_banner(self, review):
        self.assertIsNone(trusted_latest_review(["page"], self.financial, 2, self.state))
        review.assert_not_called()

    @patch("latest_review_gate.review_financial_evidence")
    def test_recorded_failed_review_cannot_get_pass_banner(self, review):
        self.state["status"] = "NEEDS_REVIEW"
        self.assertIsNone(trusted_latest_review(["page"], self.financial, 1, self.state))
        review.assert_not_called()

    @patch("latest_review_gate.review_financial_evidence", return_value={"status": "NEEDS_REVIEW"})
    def test_recheck_disagreement_cannot_get_pass_banner(self, review):
        self.assertIsNone(trusted_latest_review(["page"], self.financial, 1, self.state))
