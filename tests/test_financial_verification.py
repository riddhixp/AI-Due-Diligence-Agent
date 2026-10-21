
import unittest

from financial_labels import verify_revenue_automatically
from financial_metric_labels import verify_metric_automatically


class TestFinancialVerification(unittest.TestCase):

    def setUp(self):
        self.page = (
            "INCOME STATEMENTS\n"
            "Year Ended June 30\n"
            "2025 2024 2023\n"
            "Total revenue 281,724 245,122 211,915\n"
            "Gross margin 193,893 171,008 146,052\n"
            "Net income 101,832 88,136 72,361\n"
        )

    def test_revenue_current_year(self):
        result = verify_revenue_automatically(
            self.page, 2025, 281724
        )
        self.assertEqual(result["status"], "ROW_YEAR_MATCH")

    def test_revenue_prior_year(self):
        result = verify_revenue_automatically(
            self.page, 2024, 245122
        )
        self.assertEqual(result["status"], "ROW_YEAR_MATCH")

    def test_incorrect_revenue(self):
        result = verify_revenue_automatically(
            self.page, 2025, 99999
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_gross_profit_alternative_label(self):
        result = verify_metric_automatically(
            self.page, "gross_profit", 2025, 193893
        )
        self.assertEqual(result["status"], "ROW_YEAR_MATCH")

    def test_net_income(self):
        result = verify_metric_automatically(
            self.page, "net_income", 2025, 101832
        )
        self.assertEqual(result["status"], "ROW_YEAR_MATCH")

    def test_missing_fiscal_year(self):
        result = verify_revenue_automatically(
            self.page, 2022, 281724
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_ambiguous_revenue_rows(self):
        ambiguous_page = (
            "2025 2024\n"
            "Total revenue 100 90\n"
            "Net sales 80 70\n"
        )
        result = verify_revenue_automatically(
            ambiguous_page, 2025, 100
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
