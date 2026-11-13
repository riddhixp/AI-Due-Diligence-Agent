"""Offline portfolio card is synthetic, fail-closed, and never invokes a paid model."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portfolio_demo_card import main, render_demo_card


FIXTURE = {
    "status": "PASS", "execution_mode": "LOCAL_SYNTHETIC_FIXTURE_ONLY",
    "pages": 2, "expected_authoritative_page": 2,
    "expected_revenue_millions": 120, "model_calls": 0,
    "manual_streamlit_acceptance": "NOT_RUN",
}
WORKFLOW = {
    "status": "PASS", "execution_mode": "SCRIPTED_OFFLINE_NETWORK_GUARDED",
    "workflow_checks": 16, "failure_scenarios": 11, "external_api_calls": 0,
    "autonomous_model_validation": "NOT_RUN",
    "manual_streamlit_acceptance": "NOT_RUN",
}


class PortfolioDemoCardTests(unittest.TestCase):
    def test_card_states_scope_and_outstanding_work(self):
        card = render_demo_card(FIXTURE, WORKFLOW)
        self.assertIn("USD 130 million (page 1)", card)
        self.assertIn("USD 120 million (page 2)", card)
        self.assertIn("Human browser click-through | NOT RUN", card)
        self.assertIn("Live autonomous model evaluation | NOT RUN", card)
        self.assertIn("Scripted workflow checks | 16", card)
        self.assertNotIn("production ready", card.lower())

    def test_rejects_missing_or_misleading_evidence(self):
        for key, bad in (("status", "FAIL"), ("model_calls", 1),
                         ("pages", True), ("expected_revenue_millions", 130),
                         ("manual_streamlit_acceptance", "PASS")):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    render_demo_card(dict(FIXTURE, **{key: bad}), WORKFLOW)
        for key, bad in (("external_api_calls", 1), ("workflow_checks", 0),
                         ("failure_scenarios", True), ("autonomous_model_validation", "PASS"),
                         ("execution_mode", "LIVE"), ("status", "FAIL")):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    render_demo_card(FIXTURE, dict(WORKFLOW, **{key: bad}))

    def test_writes_new_card_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo-card.md"
            with patch("portfolio_demo_card.check_demo_fixture",
                       return_value=FIXTURE), \
                 patch("portfolio_demo_card.check_demo_workflow",
                       return_value=WORKFLOW), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--output", str(path)]), 0)
            card = path.read_text(encoding="utf-8")
            self.assertEqual(output.getvalue(), card)
            with patch("portfolio_demo_card.check_demo_fixture",
                       return_value=FIXTURE), \
                 patch("portfolio_demo_card.check_demo_workflow",
                       return_value=WORKFLOW), \
                 contextlib.redirect_stdout(io.StringIO()) as second:
                self.assertEqual(main(["--output", str(path)]), 1)
            self.assertEqual(json.loads(second.getvalue())["stage"], "output")
            self.assertEqual(path.read_text(encoding="utf-8"), card)

    def test_failed_checks_cannot_create_card_or_leak_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failed.md"
            with patch("portfolio_demo_card.check_demo_fixture",
                       side_effect=ValueError("private PDF text")), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--output", str(path)]), 1)
            self.assertFalse(path.exists())
            self.assertNotIn("private PDF text", output.getvalue())
            self.assertEqual(json.loads(output.getvalue())["stage"], "offline_checks")


if __name__ == "__main__":
    unittest.main()
