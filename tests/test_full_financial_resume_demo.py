"""Offline SDK financial correction demo regression tests."""
import unittest
from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from scripts.create_conflict_test_fixture import PAGE_ONE, PAGE_TWO
from full_financial_resume_demo import start_financial_resume_demo, finish_financial_resume_demo


class FullFinancialResumeDemoTests(unittest.TestCase):
    def setUp(self):
        buffer = BytesIO()
        canvas = Canvas(buffer, pagesize=letter)
        for lines in (PAGE_ONE, PAGE_TWO):
            for index, line in enumerate(lines):
                canvas.drawString(42, 745 - index * 32, line)
            canvas.showPage()
        canvas.save()
        self.pdf = buffer.getvalue()

    def test_approval_corrects_figures(self):
        session = start_financial_resume_demo(self.pdf)
        self.assertEqual(session["status"], "AWAITING_APPROVAL")
        self.assertEqual(session["financial"]["submission_attempts"]["count"], 1)
        result = finish_financial_resume_demo(session, self.pdf, True)
        self.assertTrue(result["finished"])
        self.assertEqual(result["submissions"], 2)
        self.assertEqual(result["review_status"], "PRELIMINARY_CHECKS_PASSED")
        self.assertEqual(result["corrected_revenue"], 120)
        self.assertEqual(result["external_api_calls"], 0)

    def test_rejection_preserves_old_figures(self):
        session = start_financial_resume_demo(self.pdf)
        result = finish_financial_resume_demo(session, self.pdf, False)
        self.assertEqual(result["submissions"], 1)
        self.assertEqual(result["corrected_revenue"], 130)

    def test_pdf_mismatch_rejected(self):
        session = start_financial_resume_demo(self.pdf)
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            finish_financial_resume_demo(session, b"another file", True)

    def test_repeated_decision_rejected(self):
        session = start_financial_resume_demo(self.pdf)
        finish_financial_resume_demo(session, self.pdf, True)
        with self.assertRaisesRegex(ValueError, "DECISION_ALREADY_MADE"):
            finish_financial_resume_demo(session, self.pdf, True)

    def test_real_filing_rejected(self):
        with self.assertRaises(ValueError):
            start_financial_resume_demo(b"private annual report")
