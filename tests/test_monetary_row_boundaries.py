import unittest
from source_verifier import check_statement_row_and_year


class MonetaryRowBoundaryTests(unittest.TestCase):
    def check(self, row, label='Net income', value=30):
        return check_statement_row_and_year(
            ['Fiscal years 2025 2024 2023\n' + row], value, 1, label, 2025, 0)

    def test_per_share_row_is_not_total_net_income(self):
        self.assertEqual(self.check('Net income per share 30 25 20')['status'], 'NEEDS_REVIEW')

    def test_cash_flow_margin_is_not_monetary_cash_flow(self):
        self.assertEqual(self.check('Operating cash flow margin 30 25 20',
                                   label='Operating cash flow')['status'], 'NEEDS_REVIEW')

    def test_percentage_row_is_not_a_monetary_statement_row(self):
        self.assertEqual(self.check('Gross margin 30% 25% 20%',
                                   label='Gross margin')['status'], 'NEEDS_REVIEW')

    def test_monetary_row_with_dot_leaders_still_matches(self):
        self.assertEqual(self.check('Net income ... $30 25 20')['status'], 'ROW_YEAR_MATCH')

    def test_years_after_a_case_insensitive_row_cannot_supply_its_heading(self):
        pages = ['NET INCOME 30 25 20\nUnrelated note: 2025 2024 2023']
        result = check_statement_row_and_year(pages, 30, 1, 'Net income', 2025, 0)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
