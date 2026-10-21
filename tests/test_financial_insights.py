
import unittest

from financial_insights import (
    ExtendedFinancialData,
    calculate_financial_insights,
    safe_percentage,
)


class TestFinancialInsights(unittest.TestCase):

    def setUp(self):
        self.data = ExtendedFinancialData(
            revenue_current=23769,
            revenue_previous=21505,
            gross_profit=21218,
            net_income=7130,
            operating_cash_flow=10030,
            subscription_revenue=22904,
        )

    def test_revenue_growth(self):
        result = calculate_financial_insights(self.data)
        self.assertEqual(result["revenue_growth"], 10.53)

    def test_profitability_margins(self):
        result = calculate_financial_insights(self.data)
        self.assertEqual(result["gross_margin"], 89.27)
        self.assertEqual(result["net_margin"], 30.00)

    def test_cash_conversion(self):
        result = calculate_financial_insights(self.data)
        self.assertEqual(
            result["operating_cash_conversion"], 140.67
        )

    def test_subscription_share(self):
        result = calculate_financial_insights(self.data)
        self.assertEqual(
            result["subscription_revenue_share"], 96.36
        )

    def test_missing_data(self):
        result = calculate_financial_insights(self.data)
        self.assertIsNone(result["operating_margin"])
        self.assertIsNone(result["free_cash_flow"])

    def test_free_cash_flow(self):
        self.data.capital_expenditure = 500
        result = calculate_financial_insights(self.data)
        self.assertEqual(result["free_cash_flow"], 9530)

    def test_invalid_denominator(self):
        self.assertIsNone(safe_percentage(100, 0))
        self.assertIsNone(safe_percentage(100, -10))
        self.assertIsNone(safe_percentage(None, 100))


if __name__ == "__main__":
    unittest.main()
