import unittest
from unittest.mock import patch

from offline_demo_preflight import check_demo_fixture, main


class OfflineDemoPreflightTests(unittest.TestCase):
    def test_preflight_uses_synthetic_two_page_fixture_without_model(self):
        result = check_demo_fixture()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["pages"], 2)
        self.assertEqual(result["expected_authoritative_page"], 2)
        self.assertEqual(result["expected_revenue_millions"], 120)
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["manual_streamlit_acceptance"], "NOT_RUN")

    def test_preflight_fails_closed_on_invalid_fixture(self):
        with patch("offline_demo_preflight.read_synthetic_conflict_pages",
                   return_value=["invalid", "invalid"]):
            with self.assertRaisesRegex(ValueError, "SYNTHETIC_FIXTURE_CONTENT_CHANGED"):
                check_demo_fixture()

    def test_preflight_rejects_number_only_and_swapped_pages(self):
        from scripts.create_conflict_test_fixture import PAGE_ONE, PAGE_TWO
        for pages in (["headline 130", "statement 120"],
                      ["\\n".join(PAGE_TWO), "\\n".join(PAGE_ONE)]):
            with self.subTest(pages=pages), patch(
                    "offline_demo_preflight.read_synthetic_conflict_pages",
                    return_value=pages):
                with self.assertRaisesRegex(ValueError, "SYNTHETIC_FIXTURE_CONTENT_CHANGED"):
                    check_demo_fixture()

    def test_workflow_preflight_summarizes_guarded_checks(self):
        import offline_demo_preflight
        report = {'evaluation': 'PASS', 'blocked_network_attempts': 0,
                  'suites': {'workflow': {'evaluation': 'PASS',
                                         'checks': [{'name': 'review', 'passed': True}],
                                         'external_api_calls': 0,
                                         'paid_continuation_enabled': False,
                                         'autonomous_model_validation': 'NOT_RUN'},
                             'failure_practice': {'evaluation': 'PASS',
                                                  'scenarios': [{'scenario': 'rejection',
                                                                 'expected_behavior_observed': True}],
                                                  'external_api_calls': 0,
                                                  'paid_continuation_enabled': False,
                                                  'autonomous_model_validation': 'NOT_RUN'}}}
        with patch("offline_acceptance.run_acceptance", return_value=report):
            result = offline_demo_preflight.check_demo_workflow()
        self.assertEqual(result["workflow_checks"], 1)
        self.assertEqual(result["failure_scenarios"], 1)
        self.assertEqual(result["external_api_calls"], 0)
        self.assertEqual(result["manual_streamlit_acceptance"], "NOT_RUN")

    def test_combined_cli_executes_both_preflight_checks(self):
        import contextlib
        import io
        import json
        from offline_demo_preflight import main
        with patch("offline_demo_preflight.check_demo_fixture",
                   return_value={"status": "PASS"}), \
             patch("offline_demo_preflight.check_demo_workflow",
                   return_value={"status": "PASS", "external_api_calls": 0}), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--workflow"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["workflow"]["status"], "PASS")

    def test_workflow_preflight_rejects_empty_or_misleading_summary(self):
        from offline_demo_preflight import check_demo_workflow
        for summary in ("", "Offline acceptance: PASS but unverified",
                        "Offline acceptance: FAIL"):
            with self.subTest(summary=summary), \
                 patch("offline_acceptance.run_acceptance", return_value={}), \
                 patch("offline_acceptance.acceptance_summary", return_value=summary):
                with self.assertRaisesRegex(ValueError, "OFFLINE_DEMO_WORKFLOW_FAILED"):
                    check_demo_workflow()

    def test_workflow_preflight_rejects_failed_suites(self):
        from offline_demo_preflight import check_demo_workflow
        with patch("offline_acceptance.run_acceptance",
                   return_value={"evaluation": "PASS", "suites": {}}):
            with self.assertRaisesRegex(ValueError, "OFFLINE_DEMO_WORKFLOW_FAILED"):
                check_demo_workflow()

    def test_combined_cli_identifies_failed_workflow_without_leaking_details(self):
        import contextlib
        import io
        import json
        with patch("offline_demo_preflight.check_demo_fixture",
                   return_value={"status": "PASS"}), \
             patch("offline_demo_preflight.check_demo_workflow",
                   side_effect=ValueError("private customer content")), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--workflow"]), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["failed_stage"], "workflow")
        self.assertEqual(report["error_type"], "ValueError")
        self.assertNotIn("private customer content", output.getvalue())

    def test_cli_does_not_print_exception_details(self):
        import io
        import contextlib
        with patch("offline_demo_preflight.check_demo_fixture",
                   side_effect=ValueError("private secret")), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 1)
        self.assertIn('"status": "FAIL"', output.getvalue())
        self.assertIn('"failed_stage": "fixture"', output.getvalue())
        self.assertNotIn("private secret", output.getvalue())
