
import unittest

from agent_financial_review import review_financial_evidence


class TestAgentFinancialReview(unittest.TestCase):

    def setUp(self):
        self.pages = [
            """Consolidated Statements of Income
            2025 2024 2023
            Total revenue 120 100 90
            Gross profit 80 70 60
            Net income 30 25 20
            """
        ]

        self.submitted = {
            "company": "Test Company",
            "fiscal_year": 2025,
            "currency": "USD",
            "units": "millions",
            "revenue_current": 120,
            "revenue_previous": 100,
            "gross_profit": 80,
            "net_income": 30,
            "reported": {
                "revenue_growth": 20.0,
                "gross_margin": 66.67,
                "net_margin": 25.0,
            },
            "source_pages": {
                "revenue_current": 1,
                "revenue_previous": 1,
                "gross_profit": 1,
                "net_income": 1,
            },
        }

    def test_valid_financial_data(self):
        result = review_financial_evidence(
            self.pages, self.submitted
        )

        self.assertEqual(
            result["status"],
            "PRELIMINARY_CHECKS_PASSED",
        )

    def test_incorrect_revenue_growth(self):
        self.submitted["reported"]["revenue_growth"] = 35.0

        result = review_financial_evidence(
            self.pages, self.submitted
        )

        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertEqual(
            result["arithmetic"]["revenue_growth"]["status"],
            "FAIL",
        )

    def test_missing_source_number(self):
        self.submitted["gross_profit"] = 999

        result = review_financial_evidence(
            self.pages, self.submitted
        )

        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_missing_submission(self):
        result = review_financial_evidence(self.pages, {})

        self.assertEqual(
            result["status"],
            "REVIEW_UNAVAILABLE",
        )

    def test_statement_row_and_year_match(self):
        result = review_financial_evidence(
            self.pages, self.submitted
        )

        self.assertEqual(
            len(result["statement_checks"]), 4
        )

        self.assertTrue(all(
            check["status"] == "ROW_YEAR_MATCH"
            for check in result["statement_checks"]
        ))

    def test_wrong_financial_year_value(self):
        # The number exists on the page, but belongs
        # to the previous fiscal year.
        self.submitted["revenue_current"] = 100

        # Keep arithmetic internally consistent,
        # so this tests source verification separately.
        self.submitted["reported"]["revenue_growth"] = 0.0

        result = review_financial_evidence(
            self.pages, self.submitted
        )

        current_revenue_check = next(
            check for check in result["statement_checks"]
            if check["metric"] == "Current-year revenue"
        )

        self.assertEqual(
            current_revenue_check["status"],
            "NEEDS_REVIEW"
        )

        self.assertEqual(
            result["status"],
            "NEEDS_REVIEW"
        )


    def test_unspecified_currency_and_units_require_review(self):
        self.submitted["currency"] = "unspecified"
        self.submitted["units"] = "unspecified"

        result = review_financial_evidence(
            self.pages,
            self.submitted,
        )

        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertEqual(len(result["metadata_issues"]), 2)



    def test_wrong_year_requires_source_investigation(self):
        # FY2024 revenue is incorrectly submitted as FY2025.
        # Both values exist in the document.
        self.submitted["revenue_current"] = 100
        self.submitted["reported"]["revenue_growth"] = 0.0

        result = review_financial_evidence(
            self.pages,
            self.submitted,
        )

        current_year = next(
            item for item in result["statement_checks"]
            if item["metric"] == "Current-year revenue"
        )

        self.assertEqual(current_year["status"], "NEEDS_REVIEW")
        self.assertEqual(result["status"], "NEEDS_REVIEW")

if __name__ == "__main__":
    unittest.main()
