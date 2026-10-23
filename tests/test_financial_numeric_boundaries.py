"""Undefined financial arithmetic must be reviewable and JSON-safe."""
import json
import unittest
from dataclasses import replace
from financial_validator import FinancialData, validate_financials
from financial_insights import ExtendedFinancialData, calculate_financial_insights
from financial_numbers import format_percentage
from optional_financial_validation import validate_optional_financial_data
from optional_statement_metrics import OPTIONAL_STATEMENT_METRICS


class FinancialNumericBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.data = FinancialData('Synthetic', 2025, 'USD', 'millions', 120, 100, 80, 30)
        self.reported = dict(revenue_growth=20, gross_margin=66.67, net_margin=25)

    def test_zero_prior_revenue_preserves_other_checks(self):
        result = validate_financials(replace(self.data, revenue_previous=0), self.reported)
        self.assertEqual(result['revenue_growth']['status'], 'UNAVAILABLE')
        self.assertIsNone(result['revenue_growth']['calculated'])
        self.assertEqual(result['gross_margin']['status'], 'PASS')
        self.assertEqual(result['net_margin']['status'], 'PASS')
        json.dumps(result, allow_nan=False)

    def test_nonpositive_current_revenue_cannot_produce_passed_margins(self):
        for value in [0, -120]:
            result = validate_financials(replace(self.data, revenue_current=value), self.reported)
            self.assertEqual(result['gross_margin']['status'], 'UNAVAILABLE')
            self.assertEqual(result['net_margin']['status'], 'UNAVAILABLE')

    def test_nonfinite_or_invalid_reported_metrics_cannot_pass(self):
        for value in [float('nan'), float('inf'), -float('inf'), True, '20', 10**400]:
            result = validate_financials(self.data, {**self.reported, 'revenue_growth': value})
            self.assertEqual(result['revenue_growth']['status'], 'INVALID')
            self.assertIsNone(result['revenue_growth']['reported'])
            json.dumps(result, allow_nan=False)

    def test_nonfinite_inputs_and_overflow_are_unavailable(self):
        for value in [float('nan'), float('inf'), True, '120', 10**400]:
            result = validate_financials(replace(self.data, revenue_current=value), self.reported)
            self.assertTrue(all(item['status'] == 'UNAVAILABLE' for item in result.values()))
            json.dumps(result, allow_nan=False)
        result = validate_financials(replace(self.data, gross_profit=1e308, revenue_current=1e-308), self.reported)
        self.assertEqual(result['gross_margin']['status'], 'UNAVAILABLE')

    def test_growth_does_not_round_monetary_inputs_before_ratio(self):
        result = validate_financials(replace(self.data, revenue_current=1.004, revenue_previous=1), self.reported)
        self.assertEqual(result['revenue_growth']['calculated'], 0.4)

    def test_diagnostics_never_return_nonfinite_values(self):
        data = ExtendedFinancialData(120, 100, 80, 30, operating_cash_flow=float('inf'),
            capital_expenditure=10, share_repurchases=float('nan'),
            operating_cash_flow_previous=1e308, capital_expenditure_previous=1e308,
            stock_based_compensation=float('nan'), deferred_revenue_change=float('inf'))
        result = calculate_financial_insights(data)
        self.assertIsNone(result['free_cash_flow'])
        self.assertIsNone(result['operating_cash_conversion'])
        self.assertIsNone(result['repurchases_less_free_cash_flow'])
        self.assertEqual(result['free_cash_flow_previous'], 0)
        json.dumps(result, allow_nan=False)

    def test_all_optional_metric_pairs_require_finite_values(self):
        for field, *_ in OPTIONAL_STATEMENT_METRICS:
            for value in [float('nan'), float('inf'), True]:
                with self.subTest(metric=field, value=value):
                    issues = validate_optional_financial_data(
                        {field: value, 'source_pages': {field: 1}}, 1)
                    self.assertTrue(issues)

    def test_undefined_percentages_have_clear_display_text(self):
        for value in [None, float('nan'), float('inf'), True]:
            self.assertEqual(format_percentage(value), 'Unavailable')
        self.assertEqual(format_percentage(-25), '-25.00%')
