
import hashlib
import json
import math
import tempfile
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

    # Serialize before touching the existing file; invalid values never replace it.
    payload = json.dumps(data, indent=2, allow_nan=False)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=REPORTS_DIR,
                                         prefix=f".{report_id}.", suffix=".tmp",
                                         delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(payload)
        temporary_path.replace(file_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return file_path


def load_report(pdf_bytes):
    """Load an existing analysis if one is saved."""

    report_id = get_report_id(pdf_bytes)
    file_path = REPORTS_DIR / f"{report_id}.json"

    if not file_path.exists():
        return None

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_fields, parse_constant=_reject_constant,
                          parse_float=_finite_float)
    except RecursionError as error:
        # Treat parser depth exhaustion as a corrupt cache, so the UI can show
        # its existing local-load warning without running a replacement model.
        raise ValueError("SAVED_REPORT_NESTING_TOO_DEEP") from error
    if not isinstance(data, dict):
        raise ValueError("INVALID_SAVED_REPORT")
    return data


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_SAVED_REPORT_FIELD")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("NONFINITE_SAVED_REPORT_VALUE")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("NONFINITE_SAVED_REPORT_VALUE")
    return number
