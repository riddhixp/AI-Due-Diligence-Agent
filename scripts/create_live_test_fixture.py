"""Generate a harmless synthetic PDF for manual, paid live-agent evaluation.

Usage:
    python scripts/create_live_test_fixture.py

This file only creates a local PDF; it does NOT call an AI API.
The financial example is intentionally simple and is not a real company.
"""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas


REPORT_LINES = (
    "ILLUSTRATIVE SOFTWARE COMPANY — SYNTHETIC FY2025 FILING",
    "Training-only data. Not a real financial report.",
    "Reporting currency: USD. Monetary amounts: millions.",
    "Consolidated Statements of Income",
    "Fiscal years 2025 2024 2023",
    "Total revenue 120 100 90",
    "Gross profit 80 70 60",
    "Net income 30 25 20",
    "Business overview",
    "Subscription-based cloud software. Retention metrics not disclosed.",
    "Technology and security",
    "No independent cybersecurity report or scalability test provided.",
)


def create_fixture(destination):
    """Create a one-page PDF and return its absolute filesystem path."""
    path = Path(destination).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(path), pagesize=letter)
    canvas.setFont("Helvetica", 11)
    for index, line in enumerate(REPORT_LINES):
        canvas.drawString(42, 745 - index * 30, line.replace("—", "-"))
    canvas.save()
    return path


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "synthetic_live_test.pdf"
    print("Created synthetic test PDF:", create_fixture(output))
    print("No AI API request was made.")
