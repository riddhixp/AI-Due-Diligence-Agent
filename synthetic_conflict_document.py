"""Read only the public synthetic conflict fixture; never invoke a model."""
from io import BytesIO
from pypdf import PdfReader


def read_synthetic_conflict_pages(pdf_bytes):
    try:
        pages = [page.extract_text() or '' for page in PdfReader(BytesIO(pdf_bytes)).pages]
    except Exception as error:
        raise ValueError('SYNTHETIC_CONFLICT_PDF_REQUIRED') from error
    if (len(pages) != 2
            or 'SYNTHETIC CONFLICT TEST - NOT A REAL COMPANY' not in pages[0]
            or not all(line in pages[1] for line in (
                'Fiscal years 2025 2024 2023', 'Total revenue 120 100 90',
                'Gross profit 80 70 60', 'Net income 30 25 20',
                'The authoritative FY2025 total revenue figure is 120'))):
        raise ValueError('SYNTHETIC_CONFLICT_PDF_REQUIRED')
    return pages
