"""Regression checks for the read-only portfolio release status."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from portfolio_readiness import assess_readiness, main


class PortfolioReadinessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {
            "status": "PASS",
            "execution_mode": "LOCAL_SYNTHETIC_FIXTURE_ONLY",
            "pages": 2,
            "expected_authoritative_page": 2,
            "expected_revenue_millions": 120,
            "model_calls": 0,
            "manual_streamlit_acceptance": "NOT_RUN",
        }
        self.workflow = {
            "status": "PASS",
            "execution_mode": "SCRIPTED_OFFLINE_NETWORK_GUARDED",
            "workflow_checks": 16,
            "failure_scenarios": 11,
            "external_api_calls": 0,
            "autonomous_model_validation": "NOT_RUN",
            "manual_streamlit_acceptance": "NOT_RUN",
        }

    def test_success_never_overstates_validation(self):
        result = assess_readiness(self.fixture, self.workflow)
        self.assertEqual(result["status"], "OFFLINE_REHEARSAL_READY")
        self.assertEqual(result["workflow_checks"], 16)
        self.assertEqual(result["external_api_calls"], 0)
        self.assertEqual(result["manual_browser_acceptance"], "NOT_RUN")
        self.assertEqual(result["autonomous_model_validation"], "NOT_RUN")
        self.assertEqual(result["paid_continuation"], "DISABLED")
        self.assertIs(result["production_ready"], False)
        self.assertIs(result["portfolio_demo_fully_validated"], False)

    def test_untrusted_pass_claims_cannot_upgrade_status(self):
        mutations = [
            ("fixture", "model_calls", True),
            ("fixture", "manual_streamlit_acceptance", "PASS"),
            ("fixture", "expected_revenue_millions", 130),
            ("workflow", "external_api_calls", 1),
            ("workflow", "workflow_checks", 0),
            ("workflow", "autonomous_model_validation", "PASS"),
            ("workflow", "manual_streamlit_acceptance", "PASS"),
        ]
        for part, key, value in mutations:
            with self.subTest(part=part, key=key):
                fixture, workflow = self.fixture.copy(), self.workflow.copy()
                (fixture if part == "fixture" else workflow)[key] = value
                with self.assertRaisesRegex(ValueError, "INVALID_PORTFOLIO_DEMO_EVIDENCE"):
                    assess_readiness(fixture, workflow)

    def test_cli_renders_valid_status(self):
        with patch("portfolio_readiness.check_demo_fixture", return_value=self.fixture), \
             patch("portfolio_readiness.check_demo_workflow", return_value=self.workflow), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "OFFLINE_REHEARSAL_READY")
        self.assertFalse(report["portfolio_demo_fully_validated"])

    def test_cli_fails_closed_without_sensitive_exception_text(self):
        with patch("portfolio_readiness.check_demo_fixture",
                   side_effect=ValueError("private client PDF text")), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["production_ready"])
        self.assertNotIn("private client PDF text", output.getvalue())

    def test_verified_package_is_explicit_but_not_a_live_validation(self):
        package = {
            "status": "PASS",
            "integrity": "VERIFIED",
            "scope": "SYNTHETIC_OFFLINE_DEMO_ONLY",
            "external_api_calls": 0,
            "manual_streamlit_acceptance": "NOT_RUN",
            "autonomous_model_validation": "NOT_RUN",
        }
        report = assess_readiness(self.fixture, self.workflow, package)
        self.assertEqual(report["demo_package_integrity"], "VERIFIED")
        self.assertFalse(report["portfolio_demo_fully_validated"])
        self.assertEqual(report["manual_browser_acceptance"], "NOT_RUN")
        self.assertEqual(report["paid_continuation"], "DISABLED")

    def test_package_evidence_must_match_all_offline_safeguards(self):
        package = {
            "status": "PASS",
            "integrity": "VERIFIED",
            "scope": "SYNTHETIC_OFFLINE_DEMO_ONLY",
            "external_api_calls": 0,
            "manual_streamlit_acceptance": "NOT_RUN",
            "autonomous_model_validation": "NOT_RUN",
        }
        for name, replacement in (
            ("status", "FAIL"),
            ("integrity", "NOT_CHECKED"),
            ("scope", "PRODUCTION"),
            ("external_api_calls", True),
            ("external_api_calls", 1),
            ("manual_streamlit_acceptance", "PASS"),
            ("autonomous_model_validation", "PASS"),
        ):
            with self.subTest(name=name, replacement=replacement):
                candidate = dict(package, **{name: replacement})
                with self.assertRaisesRegex(ValueError, "INVALID_PORTFOLIO_PACKAGE_EVIDENCE"):
                    assess_readiness(self.fixture, self.workflow, candidate)
        self.assertEqual(
            assess_readiness(self.fixture, self.workflow)["demo_package_integrity"],
            "NOT_CHECKED",
        )

    def test_cli_verifies_package_when_directory_provided(self):
        package = {
            "status": "PASS", "integrity": "VERIFIED",
            "scope": "SYNTHETIC_OFFLINE_DEMO_ONLY",
            "external_api_calls": 0,
            "manual_streamlit_acceptance": "NOT_RUN",
            "autonomous_model_validation": "NOT_RUN",
        }
        with patch("portfolio_readiness.check_demo_fixture", return_value=self.fixture), \
             patch("portfolio_readiness.check_demo_workflow", return_value=self.workflow), \
             patch("portfolio_readiness.verify_demo", return_value=package) as verify, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--directory", "demo-run"]), 0)
        self.assertEqual(str(verify.call_args.args[0]), "demo-run")
        self.assertEqual(
            json.loads(output.getvalue())["demo_package_integrity"], "VERIFIED")

    def test_cli_refuses_tampered_demo_package(self):
        with patch("portfolio_readiness.check_demo_fixture", return_value=self.fixture), \
             patch("portfolio_readiness.check_demo_workflow", return_value=self.workflow), \
             patch("portfolio_readiness.verify_demo",
                   side_effect=ValueError("private PDF text")), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--directory", "tampered-demo"]), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "BLOCKED")
        self.assertNotIn("private PDF text", output.getvalue())
