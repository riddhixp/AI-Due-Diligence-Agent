import unittest

from correction_changes import financial_correction_changes


class CorrectionChangesTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "company": "Demo", "revenue_current": 120,
            "currency": "USD", "units": "millions",
            "reported": {"revenue_growth": 20},
            "source_pages": {"revenue_current": 1},
        }

    def test_first_submission_allowed(self):
        self.assertTrue(financial_correction_changes({}, self.original))

    def test_identical_revision_rejected(self):
        self.assertFalse(financial_correction_changes(
            self.original, dict(self.original)))

    def test_company_name_only_does_not_count_as_correction(self):
        new = dict(self.original, company="Different name")
        self.assertFalse(financial_correction_changes(self.original, new))

    def test_revised_revenue_counts(self):
        new = dict(self.original, revenue_current=130)
        self.assertTrue(financial_correction_changes(self.original, new))

    def test_corrected_page_counts(self):
        new = dict(self.original, source_pages={"revenue_current": 2})
        self.assertTrue(financial_correction_changes(self.original, new))

    def test_corrected_units_counts(self):
        new = dict(self.original, units="thousands")
        self.assertTrue(financial_correction_changes(self.original, new))


if __name__ == "__main__":
    unittest.main()
