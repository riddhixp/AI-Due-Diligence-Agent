
import unittest

from source_verifier import (
    verify_figure,
    verify_financial_data,
)


class TestSourceVerifier(unittest.TestCase):

    def setUp(self):
        self.pages = [
            "Revenue 23,769 and 21,505.\n"
            "Gross profit 21,218.\n"
            "Net income 7,130.",
            "Other financial information.",
        ]

    def test_correct_figure(self):
        result = verify_figure(self.pages, 23769, 1)
        self.assertEqual(result["status"], "NUMBER_FOUND")

    def test_incorrect_figure(self):
        result = verify_figure(self.pages, 99999, 1)
        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_invalid_page(self):
        result = verify_figure(self.pages, 23769, 100)
        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_multiple_financial_figures(self):
        financial_data = {
            "revenue_current": 23769,
            "revenue_previous": 21505,
            "gross_profit": 21218,
            "net_income": 7130,
            "source_pages": {
                "revenue_current": 1,
                "revenue_previous": 1,
                "gross_profit": 1,
                "net_income": 1,
            },
        }

        results = verify_financial_data(
            self.pages, financial_data
        )

        self.assertEqual(len(results), 4)

        for result in results:
            self.assertEqual(
                result["Result"],
                "NUMBER_FOUND",
            )

    def test_missing_source_page(self):
        financial_data = {
            "revenue_current": 23769,
            "revenue_previous": 21505,
            "gross_profit": 21218,
            "net_income": 7130,
        }

        results = verify_financial_data(
            self.pages, financial_data
        )

        for result in results:
            self.assertEqual(
                result["Result"],
                "NEEDS_REVIEW",
            )


if __name__ == "__main__":
    unittest.main()
