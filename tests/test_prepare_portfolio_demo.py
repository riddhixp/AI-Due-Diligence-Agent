"""No-provider tests for the single-command synthetic portfolio demo setup."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prepare_portfolio_demo import main, prepare_demo


class PreparePortfolioDemoTests(unittest.TestCase):
    def test_generates_both_assets_without_provider(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("socket.socket.connect", side_effect=AssertionError("NETWORK_FORBIDDEN")):
                result = prepare_demo(folder)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["external_api_calls"], 0)
            self.assertEqual(result["manual_streamlit_acceptance"], "NOT_RUN")
            pdf = Path(folder) / "synthetic_conflict_test.pdf"
            card = Path(folder) / "demo-card.md"
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
            self.assertIn("USD 120 million (page 2)", card.read_text(encoding="utf-8"))
            self.assertIn("Human browser click-through | NOT RUN", card.read_text(encoding="utf-8"))

    def test_documented_module_cli_runs_in_fresh_python_process(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as folder:
            completed = subprocess.run(
                [sys.executable, "-m", "prepare_portfolio_demo",
                 "--directory", folder],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["external_api_calls"], 0)
            self.assertTrue((Path(folder) / "demo-manifest.json").is_file())

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / "synthetic_conflict_test.pdf"
            pdf.write_bytes(b"keep existing")
            with self.assertRaises(FileExistsError):
                prepare_demo(folder)
            self.assertEqual(pdf.read_bytes(), b"keep existing")
            self.assertFalse((Path(folder) / "demo-card.md").exists())

    def test_failing_checks_do_not_create_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("prepare_portfolio_demo.check_demo_workflow",
                       side_effect=ValueError("private failure")):
                with self.assertRaises(ValueError):
                    prepare_demo(folder)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_generated_pdf_with_header_but_wrong_statements_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("prepare_portfolio_demo.create_conflict_fixture") as create:
                def make_misleading_pdf(destination):
                    destination = Path(destination)
                    destination.write_bytes(b"%PDF-1.4\\nnot a valid PDF")
                    return destination
                create.side_effect = make_misleading_pdf
                with self.assertRaisesRegex(ValueError, "INVALID_SYNTHETIC_DEMO_PDF"):
                    prepare_demo(folder)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_swapped_or_missing_generated_page_content_is_rejected(self):
        from scripts.create_conflict_test_fixture import PAGE_ONE, PAGE_TWO
        with tempfile.TemporaryDirectory() as folder:
            for pages in (["\\n".join(PAGE_TWO), "\\n".join(PAGE_ONE)],
                          ["\\n".join(PAGE_ONE), "Total revenue 120 100 90"]):
                with self.subTest(pages=pages), \
                     patch("prepare_portfolio_demo.read_synthetic_conflict_pages",
                           return_value=pages):
                    with self.assertRaisesRegex(ValueError, "INVALID_SYNTHETIC_DEMO_PDF"):
                        prepare_demo(folder)
                    self.assertEqual(list(Path(folder).iterdir()), [])

    def test_second_write_failure_rolls_back_created_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / "synthetic_conflict_test.pdf"
            card = Path(folder) / "demo-card.md"
            original_open = Path.open

            def guarded_open(path, *args, **kwargs):
                if path.name == "demo-card.md" and args and args[0] == "x":
                    raise OSError("private write failure")
                return original_open(path, *args, **kwargs)

            with patch("prepare_portfolio_demo.Path.open", new=guarded_open):
                with self.assertRaises(OSError):
                    prepare_demo(folder)
            self.assertFalse(pdf.exists())
            self.assertFalse(card.exists())

    def test_cli_reports_only_safe_failure_type(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("prepare_portfolio_demo.check_demo_fixture",
                       side_effect=RuntimeError("private company text")), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--directory", folder]), 1)
            report = json.loads(output.getvalue())
            self.assertEqual(report["error_type"], "RuntimeError")
            self.assertNotIn("private company text", output.getvalue())
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
