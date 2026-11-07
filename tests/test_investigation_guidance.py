import unittest

from investigation_guidance import investigation_next_actions


class InvestigationGuidanceTests(unittest.TestCase):
    def test_no_review(self):
        self.assertIn("Submit", investigation_next_actions(None)[0])

    def test_preliminary_pass_does_not_claim_audit(self):
        actions = investigation_next_actions({"status": "PRELIMINARY_CHECKS_PASSED"})
        self.assertIn("not describe", actions[0])

    def test_arithmetic_failure_produces_calculation_action(self):
        actions = investigation_next_actions({
            "status": "NEEDS_REVIEW",
            "arithmetic": {"revenue_growth": {"status": "FAIL"}},
        })
        self.assertTrue(any("revenue_growth" in item for item in actions))

    def test_wrong_year_produces_statement_action(self):
        actions = investigation_next_actions({
            "status": "NEEDS_REVIEW",
            "statement_checks": [{
                "metric": "Current-year revenue", "status": "NEEDS_REVIEW",
            }],
        })
        self.assertTrue(any("fiscal-year column" in item for item in actions))

    def test_source_failure_produces_page_action(self):
        actions = investigation_next_actions({
            "status": "NEEDS_REVIEW",
            "sources": [{"Result": "NUMBER_NOT_FOUND"}],
        })
        self.assertTrue(any("page references" in item for item in actions))

    def test_unknown_currency_must_not_be_fabricated(self):
        actions = investigation_next_actions({
            "status": "NEEDS_REVIEW",
            "metadata_issues": ["currency not established"],
        })
        self.assertTrue(any("unspecified" in item for item in actions))

    def test_deduplicates_repeated_missing_statement_metric(self):
        actions = investigation_next_actions({
            "status": "NEEDS_REVIEW",
            "statement_checks": [
                {"metric": "Revenue", "status": "NEEDS_REVIEW"},
                {"metric": "Revenue", "status": "NEEDS_REVIEW"},
            ],
        })
        self.assertEqual(len(actions), 1)


if __name__ == "__main__":
    unittest.main()
