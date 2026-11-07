"""Offline checks for SDK function-tool approval declaration.

No model runs are started and no API credentials are accessed.
"""
import unittest
from agents import function_tool


class FinancialApprovalDeclarationTests(unittest.TestCase):
    def test_approval_is_attached_before_tool_execution(self):
        called = []
        @function_tool(needs_approval=True)
        def submit_fixture(value: float) -> str:
            called.append(value)
            return "accepted"

        self.assertTrue(submit_fixture.needs_approval)
        self.assertEqual(called, [])

    def test_normal_tool_mode_remains_available(self):
        @function_tool(needs_approval=False)
        def submit_fixture(value: float) -> str:
            return "accepted"

        self.assertFalse(submit_fixture.needs_approval)


if __name__ == "__main__":
    unittest.main()
