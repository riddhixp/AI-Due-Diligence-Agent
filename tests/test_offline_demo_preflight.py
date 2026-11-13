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

    def test_cli_can_save_a_synthetic_acceptance_snapshot_without_overwriting(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "demo-check.json"
            with patch("offline_demo_preflight.check_demo_fixture",
                       return_value={"status": "PASS", "model_calls": 0,
                                     "manual_streamlit_acceptance": "NOT_RUN"}), \
                 patch("offline_demo_preflight.check_demo_workflow",
                       return_value={"status": "PASS", "external_api_calls": 0}), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--workflow", "--output", str(path)]), 0)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "PASS")
            self.assertEqual(saved["workflow"]["external_api_calls"], 0)
            self.assertEqual(saved["manual_streamlit_acceptance"], "NOT_RUN")
            self.assertEqual(json.loads(output.getvalue()), saved)
            with contextlib.redirect_stdout(io.StringIO()) as second:
                self.assertEqual(main(["--output", str(path)]), 1)
            self.assertEqual(json.loads(second.getvalue())["failed_stage"], "output")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), saved)

    def test_snapshot_serialization_error_leaves_no_file(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "not-created.json"
            real_dumps = json.dumps

            def fail_snapshot_dumps(value, *args, **kwargs):
                if isinstance(value, dict) and value.get("status") == "PASS":
                    raise TypeError("sensitive formatting exception")
                return real_dumps(value, *args, **kwargs)

            with patch("offline_demo_preflight.check_demo_fixture",
                       return_value={"status": "PASS"}), \
                 patch("offline_demo_preflight.json.dumps",
                       side_effect=fail_snapshot_dumps), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--output", str(target)]), 1)
            self.assertFalse(target.exists())
            self.assertEqual(json.loads(output.getvalue())["failed_stage"], "output")
            self.assertNotIn("sensitive formatting exception", output.getvalue())

    def test_snapshot_partial_write_is_removed(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "partial.json"
            original_open = Path.open

            class InterruptedFile:
                def __init__(self, path, *args, **kwargs):
                    self.handle = original_open(path, *args, **kwargs)

                def __enter__(self):
                    self.handle.__enter__()
                    return self

                def write(self, content):
                    self.handle.write(content[:8])
                    raise OSError("private disk failure")

                def __exit__(self, *args):
                    return self.handle.__exit__(*args)

            with patch("offline_demo_preflight.check_demo_fixture",
                       return_value={"status": "PASS"}), \
                 patch("offline_demo_preflight.Path.open",
                       side_effect=lambda path, *a, **kw: InterruptedFile(path, *a, **kw)), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--output", str(target)]), 1)
            self.assertFalse(target.exists())
            self.assertEqual(json.loads(output.getvalue())["failed_stage"], "output")
            self.assertNotIn("private disk failure", output.getvalue())

    def test_failed_preflight_does_not_create_snapshot(self):
        import contextlib
        import io
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "should-not-exist.json"
            with patch("offline_demo_preflight.check_demo_fixture",
                       side_effect=ValueError("private extracted text")), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--output", str(path)]), 1)
            self.assertFalse(path.exists())
            self.assertNotIn("private extracted text", output.getvalue())

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
