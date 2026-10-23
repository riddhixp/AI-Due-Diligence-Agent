import unittest
from source_verifier import extract_numbers, normalise_number, verify_figure, extract_evidence_context
from agent_financial_review import review_financial_evidence
from synthetic_financial_fixture import PAGES, supported_submission
from financial_insights import ExtendedFinancialData, calculate_financial_insights


class SignedFinancialEvidenceTests(unittest.TestCase):
    def test_parentheses_and_currency_preserve_negative_sign(self):
        self.assertEqual(extract_numbers('Cash flows (1,200) £(30) (€ 4.50) -$6 $-7 −8 +9'),
                         [-1200, -30, -4.5, -6, -7, -8, 9])
        self.assertEqual(normalise_number('(£1,200.50)'), -1200.5)

    def test_positive_number_cannot_match_parenthesized_outflow(self):
        pages = ['Operating cash flow (60) 50 45']
        self.assertEqual(verify_figure(pages, 60, 1)['status'], 'NEEDS_REVIEW')
        self.assertEqual(verify_figure(pages, -60, 1)['status'], 'NUMBER_FOUND')
        self.assertIsNone(extract_evidence_context(pages, 60, 1))
        self.assertIsNotNone(extract_evidence_context(pages, -60, 1))

    def test_loss_cannot_be_verified_as_positive_income(self):
        submitted = supported_submission()
        pages = [PAGES[0].replace('Net income 30 25 20', 'Net income (30) 25 20')]
        self.assertEqual(review_financial_evidence(pages, submitted)['status'], 'NEEDS_REVIEW')
        submitted['net_income'] = -30
        submitted['reported']['net_margin'] = -25
        self.assertEqual(review_financial_evidence(pages, submitted)['status'], 'PRELIMINARY_CHECKS_PASSED')

    def test_capex_outflow_can_be_explicitly_verified_as_positive_spend(self):
        submitted = supported_submission()
        submitted['capital_expenditure'] = 10
        submitted['source_pages']['capital_expenditure'] = 2
        pages = PAGES + ['Fiscal years 2025 2024 2023\nPurchases of property and equipment (10) (8) (7)']
        result = review_financial_evidence(pages, submitted)
        self.assertEqual(result['status'], 'PRELIMINARY_CHECKS_PASSED')
        check = next(item for item in result['statement_checks'] if item['metric'] == 'Capital expenditure')
        self.assertEqual(check['normalization'], 'CASH_OUTFLOW_MAGNITUDE')

    def test_operating_cash_outflow_is_never_normalized_to_positive(self):
        submitted = supported_submission()
        submitted['operating_cash_flow'] = 60
        submitted['source_pages']['operating_cash_flow'] = 2
        pages = PAGES + ['Fiscal years 2025 2024 2023\nNet cash used in operating activities (60) 50 45']
        self.assertEqual(review_financial_evidence(pages, submitted)['status'], 'NEEDS_REVIEW')
        submitted['operating_cash_flow'] = -60
        self.assertEqual(review_financial_evidence(pages, submitted)['status'], 'PRELIMINARY_CHECKS_PASSED')

    def test_negative_capex_does_not_increase_calculated_free_cash_flow(self):
        data = ExtendedFinancialData(revenue_current=120, revenue_previous=100,
            gross_profit=80, net_income=30, operating_cash_flow=60, capital_expenditure=-10,
            operating_cash_flow_previous=50, capital_expenditure_previous=-8,
            operating_cash_flow_two_years_ago=45, capital_expenditure_two_years_ago=-7)
        result = calculate_financial_insights(data)
        self.assertIsNone(result['free_cash_flow'])
        self.assertIsNone(result['free_cash_flow_previous'])
        self.assertIsNone(result['free_cash_flow_two_years_ago'])

    def test_negative_spend_input_requires_reconciliation(self):
        submitted = supported_submission()
        submitted['capital_expenditure'] = -10
        submitted['source_pages']['capital_expenditure'] = 2
        pages = PAGES + ['Fiscal years 2025 2024 2023\nPurchases of property and equipment (10) (8) (7)']
        self.assertEqual(review_financial_evidence(pages, submitted)['status'], 'NEEDS_REVIEW')

    def test_incomplete_parentheses_and_nonfinite_numbers_are_not_rescued(self):
        self.assertEqual(extract_numbers('Unmatched (30 and 40)'), [])
        self.assertIsNone(normalise_number('NaN'))
        self.assertIsNone(normalise_number('Infinity'))

    def test_numeric_note_cannot_be_treated_as_first_year_loss(self):
        from source_verifier import check_statement_row_and_year
        result = check_statement_row_and_year(
            ['Fiscal years 2025 2024 2023\nNet income (3) 30 25 20'],
            -3, 1, 'Net income', 2025, 0)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_normalized_spend_is_disclosed_and_other_cash_signs_are_retained(self):
        from verification_notice import final_verification_notice
        submitted = supported_submission()
        submitted.update(operating_cash_flow=-60, capital_expenditure=10, share_repurchases=5)
        submitted['source_pages'].update(operating_cash_flow=2, capital_expenditure=2, share_repurchases=2)
        pages = PAGES + ['Fiscal years 2025 2024 2023\n'
            'Net cash used in operating activities (60) (50) 45\n'
            'Purchases of property and equipment (10) (8) (7)\n'
            'Repurchases of common stock (5) (4) (3)']
        review = review_financial_evidence(pages, submitted)
        self.assertEqual(review['status'], 'PRELIMINARY_CHECKS_PASSED')
        self.assertIn('positive cash-spending', final_verification_notice(submitted, review)[1])
        data = ExtendedFinancialData(revenue_current=120, revenue_previous=100,
            gross_profit=80, net_income=30, operating_cash_flow=-60, capital_expenditure=10)
        self.assertEqual(calculate_financial_insights(data)['free_cash_flow'], -70)
