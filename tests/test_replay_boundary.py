import unittest
from replay_boundary import validate_replay_boundary


class ReplayBoundaryTests(unittest.TestCase):
    def test_balanced_tool_exchange(self):
        items = [
            {"type": "message", "role": "user", "content": "test"},
            {"type": "function_call", "call_id": "one"},
            {"type": "function_call_output", "call_id": "one"},
        ]
        result = validate_replay_boundary(items)
        self.assertTrue(result["safe_boundary"])
        self.assertFalse(result["can_resume"])

    def test_pending_tool_call_rejected(self):
        result = validate_replay_boundary([
            {"type": "function_call", "call_id": "one"}
        ])
        self.assertEqual(result["reason"], "PENDING_TOOL_CALL")

    def test_orphan_output_rejected(self):
        result = validate_replay_boundary([
            {"type": "function_call_output", "call_id": "one"}
        ])
        self.assertEqual(result["reason"], "ORPHAN_TOOL_OUTPUT")

    def test_unknown_item_rejected(self):
        self.assertFalse(validate_replay_boundary([
            {"type": "unknown"}
        ])["safe_boundary"])

    def test_empty_rejected(self):
        self.assertEqual(validate_replay_boundary([])["reason"], "EMPTY_TRANSCRIPT")


if __name__ == "__main__":
    unittest.main()
