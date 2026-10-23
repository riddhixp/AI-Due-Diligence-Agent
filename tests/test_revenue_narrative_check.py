import unittest
from revenue_narrative_check import find_reversed_revenue_arrows


class RevenueNarrativeTests(unittest.TestCase):
    def setUp(self):
        self.data = {"revenue_previous": 100, "revenue_current": 120}

    def test_reversed_arrow(self):
        result = find_reversed_revenue_arrows(
            "Revenue growth (120 → 100; +20%)", self.data)
        self.assertEqual(len(result), 1)

    def test_correct_arrow(self):
        self.assertEqual(find_reversed_revenue_arrows(
            "Revenue grew 100 → 120 (+20%)", self.data), [])

    def test_without_arrow(self):
        self.assertEqual(find_reversed_revenue_arrows(
            "FY2025 was 120, FY2024 was 100", self.data), [])

    def test_missing_data(self):
        self.assertEqual(find_reversed_revenue_arrows(
            "120 → 100", {}), [])

    def test_unrelated_financial_arrow_is_not_a_revenue_conflict(self):
        self.assertEqual(find_reversed_revenue_arrows(
            "Cash flow fell 120 → 100", self.data), [])

    def test_revenue_heading_applies_to_following_arrow(self):
        self.assertEqual(len(find_reversed_revenue_arrows(
            "## Revenue\n120 → 100", self.data)), 1)

    def test_earlier_revenue_line_does_not_relabel_cash_flow(self):
        self.assertEqual(find_reversed_revenue_arrows(
            "Revenue grew 100 → 120\nCash flow fell 120 → 100", self.data), [])


if __name__ == "__main__":
    unittest.main()
