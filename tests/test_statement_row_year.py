
import unittest

from source_verifier import check_statement_row_and_year


class TestStatementRowAndYear(unittest.TestCase):

    def setUp(self):
        self.pages = [
            """
            Consolidated Statements of Income
            Fiscal years 2025 2024 2023

            Total revenue 281724 245122 211915
            Gross profit 193893 171008 146052
            Net income 101832 88136 72361
            """
        ]

    def test_correct_year_and_value(self):
        result = check_statement_row_and_year(
            self.pages, 281724, 1,
            "Total revenue", 2025, 0
        )
        self.assertEqual(result["status"], "ROW_YEAR_MATCH")

    def test_wrong_year_value(self):
        result = check_statement_row_and_year(
            self.pages, 245122, 1,
            "Total revenue", 2025, 0
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_correct_previous_year(self):
        result = check_statement_row_and_year(
            self.pages, 245122, 1,
            "Total revenue", 2024, 1
        )
        self.assertEqual(result["status"], "ROW_YEAR_MATCH")


if __name__ == "__main__":
    unittest.main()
