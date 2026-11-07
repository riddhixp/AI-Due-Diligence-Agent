import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from scripts.create_live_test_fixture import create_fixture


class LiveTestFixtureTests(unittest.TestCase):
    def test_pdf_contains_expected_statement_and_units(self):
        with tempfile.TemporaryDirectory() as directory:
            path = create_fixture(Path(directory) / "synthetic.pdf")
            self.assertTrue(path.is_file())
            self.assertEqual(len(PdfReader(str(path)).pages), 1)
            text = PdfReader(str(path)).pages[0].extract_text()
            self.assertIn("Reporting currency: USD", text)
            self.assertIn("Total revenue 120 100 90", text)
            self.assertIn("Gross profit 80 70 60", text)
            self.assertIn("Net income 30 25 20", text)

    def test_recreating_file_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            create_fixture(path)
            create_fixture(path)
            self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
