"""Create a contradictory-report fixture to test source prioritisation.

The first page deliberately contains an incorrect headline. Page two contains
the authoritative financial statement. The agent should verify against page 2.
This evaluates conflict detection, not guaranteed two-submission correction.
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas


PAGE_ONE = (
    "SYNTHETIC CONFLICT TEST - NOT A REAL COMPANY",
    "Illustrative Software Company, FY2025",
    "Management highlights (UNAUDITED AND UNRECONCILED)",
    "A draft summary states FY2025 revenue of USD 130 million.",
    "NOTE: headline figures are provisional and may contain errors.",
    "Consult the financial statements on page 2 before citing results.",
    "Business overview: subscription cloud software.",
    "Retention metrics and independent security reports are unavailable.",
)
PAGE_TWO = (
    "SYNTHETIC CONSOLIDATED STATEMENT OF INCOME",
    "Currency USD; monetary amounts in millions.",
    "Fiscal years 2025 2024 2023",
    "Total revenue 120 100 90",
    "Gross profit 80 70 60",
    "Net income 30 25 20",
    "The authoritative FY2025 total revenue figure is 120, not 130.",
)


def create_conflict_fixture(destination):
    path = Path(destination).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = Canvas(str(path), pagesize=letter)
    for page in (PAGE_ONE, PAGE_TWO):
        pdf.setFont("Helvetica", 11)
        for index, line in enumerate(page):
            pdf.drawString(42, 745 - index * 32, line)
        pdf.showPage()
    pdf.save()
    return path


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "synthetic_conflict_test.pdf"
    print("Created:", create_conflict_fixture(target))
    print("Expected FY2025 revenue: USD 120 million (PDF page 2).")
    print("Misleading provisional headline: USD 130 million (PDF page 1).")
    print("No API call was made.")
