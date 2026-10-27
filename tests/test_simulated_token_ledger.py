import copy
import pickle
import unittest
from concurrent.futures import ThreadPoolExecutor

from simulated_token_ledger import SimulatedTokenLedger


class SimulatedTokenLedgerTests(unittest.TestCase):
    def test_limits_and_invalid_usage_fail_closed(self):
        for limit in (None, True, 0, -1, 1.5):
            with self.subTest(limit=limit), self.assertRaisesRegex(
                    ValueError, "INVALID_SIMULATED_TOKEN_LIMIT"):
                SimulatedTokenLedger(limit, 5)
        ledger = SimulatedTokenLedger(10, 10)
        for usage in ((True, 1), (-1, 1), (1.2, 0), (None, 0)):
            with self.subTest(usage=usage), self.assertRaisesRegex(
                    ValueError, "INVALID_SIMULATED_TOKEN_USAGE"):
                ledger.record(*usage)
        self.assertEqual(ledger.snapshot()["requests_recorded"], 0)

    def test_copy_and_pickle_cannot_fork_accounting(self):
        ledger = SimulatedTokenLedger(2, 2)
        ledger.record(1, 1)
        for operation in (copy.copy, copy.deepcopy):
            with self.subTest(operation=operation.__name__), self.assertRaisesRegex(
                    ValueError, "SIMULATED_TOKEN_LEDGER_CANNOT_BE_COPIED"):
                operation(ledger)
        with self.assertRaisesRegex(ValueError, "SIMULATED_TOKEN_LEDGER_CANNOT_BE_SERIALIZED"):
            pickle.dumps(ledger)
        self.assertEqual(ledger.snapshot()["requests_recorded"], 1)
        self.assertEqual(ledger.record(1, 1)["input_remaining"], 0)

    def test_normal_reassignment_cannot_reset_shared_state(self):
        ledger = SimulatedTokenLedger(2, 2)
        ledger.record(1, 1)
        replacements = {"_limits": (200, 200), "_totals": [0, 0],
                        "_requests": 0, "_lock": None}
        for field, value in replacements.items():
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "SIMULATED_TOKEN_LEDGER_STATE_IMMUTABLE"):
                setattr(ledger, field, value)
        self.assertEqual(ledger.record(1, 1)["requests_recorded"], 2)
        with self.assertRaisesRegex(ValueError, "SIMULATED_TOKEN_LIMIT_EXCEEDED"):
            ledger.record(1, 1)

    def test_atomic_accounting_and_no_partial_charge(self):
        ledger = SimulatedTokenLedger(5, 3)
        snapshot = ledger.record(2, 2)
        snapshot["input_tokens"] = 999
        with self.assertRaisesRegex(ValueError, "SIMULATED_TOKEN_LIMIT_EXCEEDED"):
            ledger.record(3, 2)
        self.assertEqual(ledger.snapshot()["input_tokens"], 2)
        self.assertEqual(ledger.snapshot()["output_tokens"], 2)
        self.assertEqual(ledger.record(3, 1)["requests_recorded"], 2)
        with self.assertRaisesRegex(ValueError, "SIMULATED_TOKEN_LIMIT_EXCEEDED"):
            ledger.record(1, 0)
        self.assertFalse(ledger.snapshot()["billing_cap_enforced"])
        self.assertFalse(ledger.snapshot()["provider_usage_verified"])

    def test_concurrent_reports_cannot_exceed_limit(self):
        ledger = SimulatedTokenLedger(10, 10)

        def submit(_):
            try:
                ledger.record(1, 1)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=24) as pool:
            self.assertEqual(sum(pool.map(submit, range(50))), 10)
        self.assertEqual(ledger.snapshot()["requests_recorded"], 10)
        self.assertEqual(ledger.snapshot()["input_remaining"], 0)
