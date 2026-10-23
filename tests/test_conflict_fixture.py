import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader
from scripts.create_conflict_test_fixture import create_conflict_fixture
from agent_financial_review import review_financial_evidence
from tests.test_investigation_scenarios import supported_submission


class ConflictFixtureTests(unittest.TestCase):
    def test_conflicting_summary_and_statement_are_separate_pages(self):
        with tempfile.TemporaryDirectory() as d:
            path = create_conflict_fixture(Path(d) / "conflict.pdf")
            pages = [p.extract_text() for p in PdfReader(path).pages]
            self.assertEqual(len(pages), 2)
            self.assertIn("revenue of USD 130 million", pages[0])
            self.assertIn("Total revenue 120 100 90", pages[1])

    def test_correct_statement_value_passes_if_cited_page_two(self):
        with tempfile.TemporaryDirectory() as d:
            path = create_conflict_fixture(Path(d) / "conflict.pdf")
            pages = [p.extract_text() for p in PdfReader(path).pages]
            data = supported_submission()
            data["source_pages"] = dict.fromkeys(data["source_pages"], 2)
            self.assertEqual(
                review_financial_evidence(pages, data)["status"],
                "PRELIMINARY_CHECKS_PASSED",
            )

    def test_wrong_headline_revenue_fails_statement_check(self):
        with tempfile.TemporaryDirectory() as d:
            path = create_conflict_fixture(Path(d) / "conflict.pdf")
            pages = [p.extract_text() for p in PdfReader(path).pages]
            data = supported_submission()
            data["revenue_current"] = 130
            data["reported"]["revenue_growth"] = 30
            data["source_pages"] = dict.fromkeys(data["source_pages"], 2)
            self.assertEqual(
                review_financial_evidence(pages, data)["status"],
                "NEEDS_REVIEW",
            )


if __name__ == "__main__":
    unittest.main()
