"""Generated demo package integrity tests without provider or network calls."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prepare_portfolio_demo import prepare_demo
from verify_portfolio_demo import main, verify_demo


class VerifyPortfolioDemoTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        with patch("socket.socket.connect", side_effect=AssertionError("NETWORK_FORBIDDEN")):
            self.prepared = prepare_demo(self.root)

    def test_verified_package_has_three_assets_and_no_manual_claims(self):
        self.assertEqual(self.prepared["integrity_manifest"], "demo-manifest.json")
        self.assertEqual(set(path.name for path in self.root.iterdir()), {
            "synthetic_conflict_test.pdf", "demo-card.md", "demo-manifest.json"})
        report = verify_demo(self.root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["integrity"], "VERIFIED")
        self.assertEqual(report["external_api_calls"], 0)
        self.assertEqual(report["manual_streamlit_acceptance"], "NOT_RUN")

    def test_tampered_pdf_and_card_fail_instead_of_reporting_success(self):
        for name in ("synthetic_conflict_test.pdf", "demo-card.md"):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b" modified")
                    with self.assertRaisesRegex(ValueError, "DEMO_ASSET_INTEGRITY_FAILED"):
                        verify_demo(self.root)
                finally:
                    path.write_bytes(original)

    def test_changed_manifest_claims_are_rejected(self):
        manifest_path = self.root / "demo-manifest.json"
        original = manifest_path.read_bytes()
        for field, value in (("external_api_calls", 1),
                             ("manual_streamlit_acceptance", "PASSED"),
                             ("scope", "PRODUCTION"), ("version", True)):
            with self.subTest(field=field):
                try:
                    data = json.loads(original)
                    data[field] = value
                    manifest_path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        verify_demo(self.root)
                finally:
                    manifest_path.write_bytes(original)

    def test_missing_asset_and_symlinked_asset_are_rejected(self):
        path = self.root / "demo-card.md"
        original = path.read_bytes()
        path.unlink()
        with self.assertRaises(ValueError):
            verify_demo(self.root)
        path.symlink_to(self.root / "demo-manifest.json")
        with self.assertRaisesRegex(ValueError, "DEMO_ASSET_INTEGRITY_FAILED"):
            verify_demo(self.root)
        path.unlink()
        path.write_bytes(original)

    def test_cli_reports_sanitized_failure(self):
        (self.root / "demo-card.md").write_text("private company text", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["--directory", str(self.root)]), 1)
        self.assertEqual(json.loads(out.getvalue())["status"], "FAIL")
        self.assertNotIn("private company text", out.getvalue())


if __name__ == "__main__":
    unittest.main()
