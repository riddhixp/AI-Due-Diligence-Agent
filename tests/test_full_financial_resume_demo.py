"""Offline SDK financial correction demo regression tests."""
import unittest
from full_financial_resume_demo import start_financial_resume_demo, finish_financial_resume_demo


class FullFinancialResumeDemoTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"%PDF SYNTHETIC CONFLICT TEST offline only"

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
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_CONFLICT_PDF_REQUIRED"):
            start_financial_resume_demo(b"private annual report")
