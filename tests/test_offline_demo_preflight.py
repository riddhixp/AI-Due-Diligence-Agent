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

    def test_cli_does_not_print_exception_details(self):
        import io
        import contextlib
        with patch("offline_demo_preflight.check_demo_fixture",
                   side_effect=ValueError("private secret")), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 1)
        self.assertIn('"status": "FAIL"', output.getvalue())
        self.assertNotIn("private secret", output.getvalue())
