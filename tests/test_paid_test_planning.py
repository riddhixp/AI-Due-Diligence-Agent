import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from paid_test_planning import prepare_paid_test_plan
from scripts.create_conflict_test_fixture import create_conflict_fixture


class PaidTestPlanningTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as folder:
            self.pdf = create_conflict_fixture(Path(folder) / 'synthetic.pdf').read_bytes()

    def test_unknown_balance_does_not_reset_original_deposit(self):
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            plan = prepare_paid_test_plan(self.pdf)
        self.assertFalse(plan['can_execute'])
        self.assertIn('REMAINING_CREDIT_UNKNOWN', plan['blockers'])
        self.assertEqual(plan['funding']['original_total_gbp'], '5.00')
        self.assertTrue(plan['funding']['includes_prior_usage'])
        self.assertIsNone(plan['funding']['remaining_credit_usd_reported'])
        self.assertFalse(plan['funding']['currency_conversion_performed'])

    def test_sufficient_reported_credit_never_authorizes_execution(self):
        plan = prepare_paid_test_plan(self.pdf, remaining_credit_usd='1.00')
        self.assertFalse(plan['can_execute'])
        self.assertEqual(plan['api_calls'], 0)
        self.assertIn('EXPLICIT_PERMISSION_FOR_THIS_TEST_REQUIRED', plan['blockers'])
        self.assertIn('PAID_CONTINUATION_DISABLED', plan['blockers'])
        self.assertFalse(plan['estimate_is_enforced_spending_cap'])

    def test_estimate_accounts_for_input_and_output_on_every_request(self):
        plan = prepare_paid_test_plan(self.pdf)
        self.assertEqual(Decimal(plan['cost_estimate_usd']), Decimal('0.064768'))
        self.assertEqual(Decimal(plan['proposed_reserve_usd']), Decimal('0.13'))
        self.assertFalse(plan['planned_limits']['reset_on_approval'])

    def test_not_enough_remaining_credit_blocks_planning_readiness(self):
        for balance in ['0', '0.12']:
            with self.subTest(balance=balance):
                plan = prepare_paid_test_plan(self.pdf, remaining_credit_usd=balance)
                self.assertIn('INSUFFICIENT_REPORTED_REMAINING_CREDIT', plan['blockers'])
                self.assertFalse(plan['funding']['new_funding_authorized'])

    def test_invalid_credit_and_limits_are_rejected(self):
        for balance in ['NaN', 'Infinity', '-1', True, 1.2, 'five pounds']:
            with self.subTest(balance=balance), self.assertRaises(ValueError):
                prepare_paid_test_plan(self.pdf, remaining_credit_usd=balance)
        for kwargs in [{'max_requests': 9}, {'max_requests': True},
                       {'max_output_tokens_per_request': 0}, {'max_input_tokens_per_request': 16001}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                prepare_paid_test_plan(self.pdf, **kwargs)

    def test_unapproved_document_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SYNTHETIC_CONFLICT_PDF_REQUIRED'):
            prepare_paid_test_plan(b'other report')
