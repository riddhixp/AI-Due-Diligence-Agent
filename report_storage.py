
import hashlib
import json
from pathlib import Path


REPORTS_DIR = Path(__file__).parent / "saved_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def get_report_id(pdf_bytes):
    """Create a unique identifier for each PDF."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def save_report(pdf_bytes, report, validation, financial_data):
    """Save a completed analysis locally."""

    report_id = get_report_id(pdf_bytes)

    data = {
        "report": report,
        "validation": validation,
        "financial_data": financial_data,
    }

    file_path = REPORTS_DIR / f"{report_id}.json"

    temporary_path = file_path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(file_path)

    return file_path


def load_report(pdf_bytes):
    """Load an existing analysis if one is saved."""

    report_id = get_report_id(pdf_bytes)
    file_path = REPORTS_DIR / f"{report_id}.json"

    if not file_path.exists():
        return None

    return json.loads(file_path.read_text(encoding="utf-8"))
