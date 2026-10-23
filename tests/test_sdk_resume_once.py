import unittest
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
