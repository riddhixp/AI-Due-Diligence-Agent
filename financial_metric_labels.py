
import re

from source_verifier import extract_numbers


METRIC_LABELS = {
    "gross_profit": [
        "gross profit",
        "gross margin",
    ],
    "net_income": [
        "net income",
        "net earnings",
        "net profit",
    ],
}


def detect_metric_label(page_text, metric):
    """
    Detect a financial metric row containing numeric values.

    If multiple candidate rows exist, return AMBIGUOUS.
    This does not verify the fiscal-year column.
    """

    labels = METRIC_LABELS.get(metric)

    if not labels:
        return {
            "status": "NEEDS_REVIEW",
            "label": None,
            "reason": "Unsupported metric.",
        }

    matches = []

    for line in page_text.splitlines():
        clean_line = line.strip().lower()

        if not extract_numbers(line):
            continue

        for label in labels:
            pattern = r"^" + re.escape(label) + r"(?=\s|[.:])"

            if re.search(pattern, clean_line):
                matches.append(label)
                break

    if len(matches) == 1:
        return {
            "status": "LABEL_FOUND",
            "label": matches[0],
            "reason": "Unique financial row identified.",
        }

    if len(matches) > 1:
        return {
            "status": "AMBIGUOUS",
            "label": None,
            "reason": "Multiple possible financial rows.",
        }

    return {
        "status": "NEEDS_REVIEW",
        "label": None,
        "reason": "No matching financial row found.",
    }


def verify_metric_automatically(
    page_text, metric, fiscal_year, expected_value
):
    """
    Detect a financial metric label and verify its value
    against the appropriate fiscal-year column.

    Supports gross_profit and net_income.
    """
    from column_detector import verify_value_by_year

    label_result = detect_metric_label(page_text, metric)

    if label_result["status"] != "LABEL_FOUND":
        return {
            "status": "NEEDS_REVIEW",
            "reason": label_result["reason"],
        }

    row_label = label_result["label"]

    result = verify_value_by_year(
        page_text=page_text,
        row_label=row_label,
        fiscal_year=fiscal_year,
        expected_value=expected_value,
    )

    result["detected_label"] = row_label

    return result

