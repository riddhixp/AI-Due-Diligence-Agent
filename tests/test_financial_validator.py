
import unittest

from financial_validator import FinancialData, validate_financials


class TestFinancialValidator(unittest.TestCase):

    def setUp(self):
        self.data = FinancialData(
            company="Example Company",
            fiscal_year=2025,
            currency="USD",
            units="millions",
            revenue_current=110,
            revenue_previous=100,
            gross_profit=88,
            net_income=22,
        )

    def test_correct_calculations(self):
        results = validate_financials(
            self.data,
            {
                "revenue_growth": 10.0,
                "gross_margin": 80.0,
                "net_margin": 20.0,
            },
        )

        for result in results.values():
            self.assertEqual(result["status"], "PASS")

    def test_incorrect_growth(self):
        results = validate_financials(
            self.data,
            {
                "revenue_growth": 20.0,
                "gross_margin": 80.0,
                "net_margin": 20.0,
            },
        )

        self.assertEqual(
            results["revenue_growth"]["status"],
            "FAIL",
        )

    def test_missing_metric(self):
        results = validate_financials(
            self.data,
            {
                "revenue_growth": 10.0,
                "gross_margin": 80.0,
            },
        )

        self.assertEqual(
            results["net_margin"]["status"],
            "MISSING",
        )


if __name__ == "__main__":
    unittest.main()
