
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import report_storage


class TestReportStorage(unittest.TestCase):

    def setUp(self):
        # Use a temporary folder, not real saved reports.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self.temp_dir.name)

        self.patcher = patch.object(
            report_storage,
            "REPORTS_DIR",
            self.reports_dir,
        )
        self.patcher.start()

        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.temp_dir.cleanup)

        self.pdf_bytes = b"sample-company-pdf"

    def test_save_and_reload(self):
        report_storage.save_report(
            self.pdf_bytes,
            "Example due diligence report",
            {"revenue_growth": {"status": "PASS"}},
            {"company": "Example Company"},
        )

        saved = report_storage.load_report(self.pdf_bytes)

        self.assertEqual(
            saved["report"],
            "Example due diligence report",
        )
        self.assertEqual(
            saved["financial_data"]["company"],
            "Example Company",
        )

    def test_unknown_pdf_returns_none(self):
        saved = report_storage.load_report(
            b"pdf-that-has-not-been-analysed"
        )
        self.assertIsNone(saved)

    def test_different_pdfs_have_different_ids(self):
        first = report_storage.get_report_id(b"company-a")
        second = report_storage.get_report_id(b"company-b")

        self.assertNotEqual(first, second)

    def test_saved_reports_are_separate(self):
        report_storage.save_report(
            b"company-a",
            "Report A",
            {},
            {},
        )

        report_storage.save_report(
            b"company-b",
            "Report B",
            {},
            {},
        )

        first = report_storage.load_report(b"company-a")
        second = report_storage.load_report(b"company-b")

        self.assertEqual(first["report"], "Report A")
        self.assertEqual(second["report"], "Report B")


if __name__ == "__main__":
    unittest.main()
