
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

    def test_boolean_page_references_are_not_valid_pdf_positions(self):
        from source_verifier import extract_evidence_context, check_statement_row_and_year
        for page in (True, False):
            with self.subTest(page=page):
                self.assertEqual(verify_figure(self.pages, 23769, page)['status'],
                                 'NEEDS_REVIEW')
                self.assertIsNone(extract_evidence_context(self.pages, 23769, page))
                self.assertEqual(check_statement_row_and_year(
                    self.pages, 23769, page, 'Revenue', 2025, 0)['status'],
                    'NEEDS_REVIEW')

    def test_boolean_statement_year_and_column_are_rejected(self):
        from source_verifier import check_statement_row_and_year
        pages = ['Fiscal years 2025 2024\\nRevenue 120 100']
        self.assertEqual(check_statement_row_and_year(
            pages, 120, 1, 'Revenue', True, 0)['status'], 'NEEDS_REVIEW')
        self.assertEqual(check_statement_row_and_year(
            pages, 120, 1, 'Revenue', 2025, False)['status'], 'NEEDS_REVIEW')

    def test_boolean_financial_amount_never_matches_numeric_pdf_token(self):
        from source_verifier import normalise_number, extract_evidence_context
        for value in (True, False):
            with self.subTest(value=value):
                self.assertIsNone(normalise_number(value))
                self.assertEqual(verify_figure(self.pages, value, 1)['status'],
                                 'NEEDS_REVIEW')
                self.assertIsNone(extract_evidence_context(self.pages, value, 1))

    def test_missing_financial_row_label_cannot_match_arbitrary_numbers(self):
        from source_verifier import check_statement_row_and_year
        pages = ['Fiscal years 2025 2024\\nRevenue 120 100']
        for label in (None, False, 1, '', '   '):
            with self.subTest(label=label):
                result = check_statement_row_and_year(
                    pages, 120, 1, label, 2025, 0)
                self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_unreadable_page_text_requires_review_instead_of_crashing(self):
        from source_verifier import check_statement_row_and_year
        for page in (None, 123, [], {'text': 'Revenue 120'}):
            with self.subTest(page=page):
                result = check_statement_row_and_year(
                    [page], 120, 1, 'Revenue', 2025, 0)
                self.assertEqual(result['status'], 'NEEDS_REVIEW')
                self.assertEqual(result['reason'], 'PDF page text is unavailable.')

    def test_statement_year_header_with_missing_column_requires_review(self):
        from source_verifier import check_statement_row_and_year
        pages = ['Fiscal years 2025 2024 2023\\nRevenue 120 100']
        result = check_statement_row_and_year(
            pages, 120, 1, 'Revenue', 2025, 0)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertIn('not aligned', result['reason'])

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
