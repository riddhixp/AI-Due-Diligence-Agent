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
