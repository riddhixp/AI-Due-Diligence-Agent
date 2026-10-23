import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from sdk_resume_once import consume_sdk_resume_state

class ResumeOnceTests(unittest.TestCase):
    def test_twice_is_blocked(self):
        class State: pass
        state = State()
        consume_sdk_resume_state(state)
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            consume_sdk_resume_state(state)

    def test_distinct_states(self):
        class State: pass
        a, b = State(), State()
        consume_sdk_resume_state(a)
        consume_sdk_resume_state(b)

    def test_unhashable_state(self):
        @dataclass
        class State:
            value: int
        state = State(1)
        consume_sdk_resume_state(state)
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            consume_sdk_resume_state(state)

    def test_concurrent_attempts_dispatch_only_once(self):
        class State: pass
        state = State()
        def attempt(_):
            try:
                consume_sdk_resume_state(state)
                return "DISPATCHED"
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(32)))
        self.assertEqual(results.count("DISPATCHED"), 1)
        self.assertEqual(results.count("SDK_RUN_STATE_ALREADY_CONSUMED"), 31)

    def test_not_weakrefable_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "NOT_WEAKREFABLE"):
            consume_sdk_resume_state([])
