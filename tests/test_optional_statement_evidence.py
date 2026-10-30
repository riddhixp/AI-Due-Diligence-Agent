"""Optional cash-flow inputs must match their own statement row and year."""
import unittest
from agent_financial_review import review_financial_evidence
from synthetic_financial_fixture import PAGES, supported_submission


class OptionalStatementEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.submitted = supported_submission()
        self.pages = PAGES + ['''Consolidated Statements of Cash Flows
Fiscal years 2025 2024 2023
Net cash provided by operating activities 60 50 45
Purchases of property and equipment 10 8 7
Repurchases of common stock 5 4 3
Stock-based compensation 8 7 6
Changes in deferred revenue 3 2 1
''']

    def submit_optional(self, field, value, page=2):
        self.submitted[field] = value
        self.submitted['source_pages'][field] = page

    def test_invented_optional_cash_flow_blocks_pass(self):
        self.submit_optional('operating_cash_flow', 999)
        self.assertEqual(review_financial_evidence(self.pages, self.submitted)['status'], 'NEEDS_REVIEW')

    def test_number_on_wrong_metric_row_is_insufficient(self):
        self.submit_optional('operating_cash_flow', 80, page=1)
        self.assertEqual(review_financial_evidence(self.pages, self.submitted)['status'], 'NEEDS_REVIEW')

    def test_current_and_historical_cash_flow_and_capex_match_own_columns(self):
        for field, value in [('operating_cash_flow', 60), ('operating_cash_flow_previous', 50),
                             ('operating_cash_flow_two_years_ago', 45), ('capital_expenditure', 10),
                             ('capital_expenditure_previous', 8), ('capital_expenditure_two_years_ago', 7),
                             ('share_repurchases', 5), ('stock_based_compensation', 8),
                             ('deferred_revenue_change', 3)]:
            self.submit_optional(field, value)
        result = review_financial_evidence(self.pages, self.submitted)
        self.assertEqual(result['status'], 'PRELIMINARY_CHECKS_PASSED')
        self.assertEqual(len(result['statement_checks']), 13)
        self.assertTrue(all(check['status'] == 'ROW_YEAR_MATCH' for check in result['statement_checks']))

    def test_prior_year_value_cannot_serve_as_current_cash_flow(self):
        self.submit_optional('operating_cash_flow', 50)
        self.assertEqual(review_financial_evidence(self.pages, self.submitted)['status'], 'NEEDS_REVIEW')

    def test_optional_value_without_its_own_page_requires_review(self):
        self.submit_optional('operating_cash_flow', 60, page=None)
        self.submitted['source_page'] = 2
        self.assertEqual(review_financial_evidence(self.pages, self.submitted)['status'], 'NEEDS_REVIEW')

    def test_missing_optional_inputs_do_not_block_required_metrics(self):
        self.submitted['operating_cash_flow'] = None
        self.submitted['source_pages']['operating_cash_flow'] = None
        result = review_financial_evidence(self.pages, self.submitted)
        self.assertEqual(result['status'], 'PRELIMINARY_CHECKS_PASSED')
        self.assertEqual(len(result['statement_checks']), 4)

    def test_operating_income_and_subscription_rows_are_verified(self):
        self.pages[0] += '\nOperating income 40 30 20\nSubscription revenue 100 80 70\n'
        self.submit_optional('operating_income', 40, page=1)
        self.submit_optional('subscription_revenue', 100, page=1)
        result = review_financial_evidence(self.pages, self.submitted)
        self.assertEqual(result['status'], 'PRELIMINARY_CHECKS_PASSED')
        self.submitted['subscription_revenue'] = 80
        self.assertEqual(review_financial_evidence(self.pages, self.submitted)['status'], 'NEEDS_REVIEW')

    def test_engine_accepts_supported_cash_flow_and_capex(self):
        import json
        from agents import set_tracing_disabled
        from due_diligence_engine import run_due_diligence
        from scripted_offline_model import ScriptedOfflineModel
        from synthetic_financial_fixture import conflict_submission_arguments
        from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
        set_tracing_disabled(True)
        fields = conflict_submission_arguments(source_page=1, revenue_current_page=1,
            revenue_previous_page=1, gross_profit_page=1, net_income_page=1,
            operating_cash_flow=60, operating_cash_flow_page=2,
            capital_expenditure=10, capital_expenditure_page=2)
        model = ScriptedOfflineModel()
        def call(name, arguments, index):
            return [ResponseFunctionToolCall(id=f'optional_f{index}', call_id=f'optional_c{index}',
                type='function_call', name=name, arguments=json.dumps(arguments), status='completed')]
        model.responses = [call('read_page', {'page_number': 1}, 1),
                           call('read_page', {'page_number': 2}, 2),
                           call('submit_financial_data', fields, 3),
                           call('review_submitted_financials', {}, 4),
                           [ResponseOutputMessage(id='optional_m', type='message', role='assistant',
                               status='completed', content=[ResponseOutputText(type='output_text',
                               text='Synthetic financial evidence reviewed.', annotations=[])])]]
        from unittest.mock import patch
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            _, validation, financial, evaluation = run_due_diligence(self.pages, offline_scripted_model=model)
        self.assertEqual(evaluation['evaluation'], 'PRELIMINARY_PASS')
        self.assertTrue(evaluation['final_eligible'])
        self.assertIsNotNone(validation)
        self.assertEqual(financial['operating_cash_flow'], 60)
        self.assertEqual(financial['capital_expenditure'], 10)
