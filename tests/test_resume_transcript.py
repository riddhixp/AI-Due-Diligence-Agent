import unittest
from types import SimpleNamespace
from resume_transcript import extract_resume_input, inspect_resume_input

class TranscriptTests(unittest.TestCase):
    def test_present_but_not_resumable(self):
        state = [{"role": "user", "content": "fixture"}]
        sample = SimpleNamespace(run_data=SimpleNamespace(input=state))
        self.assertEqual(extract_resume_input(sample), state)
        self.assertFalse(inspect_resume_input(state)["can_resume"])

    def test_absent_is_not_resumable(self):
        self.assertIsNone(extract_resume_input(Exception("limit")))
        self.assertFalse(inspect_resume_input([])["can_resume"])
