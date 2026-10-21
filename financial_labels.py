
import re


REVENUE_LABELS = [
    "total revenue",
    "total net revenues",
    "net sales",
    "total net sales",
    "net revenue",
    "revenue",
]



def detect_revenue_label(page_text):
    """
    Identify a revenue row containing financial figures.

    Ignore headings with no numbers.
    Flag multiple valid rows as ambiguous.
    """
    from source_verifier import extract_numbers

    matches = []

    for line in page_text.splitlines():
        clean_line = line.strip().lower()

        # Ignore headings without numerical values.
        if not extract_numbers(line):
            continue

        for label in REVENUE_LABELS:
            pattern = (
                r"^" + re.escape(label) + r"(?=\s|[.:])"
            )

            if re.search(pattern, clean_line):
                matches.append(label)
                break

    unique_matches = list(dict.fromkeys(matches))

    if len(matches) == 1:
        return {
            "status": "LABEL_FOUND",
            "label": matches[0],
        }

    if len(matches) > 1:
        return {
            "status": "AMBIGUOUS",
            "label": None,
        }

    return {
        "status": "NEEDS_REVIEW",
        "label": None,
    }


def verify_revenue_automatically(
    page_text, fiscal_year, expected_value
):
    """
    Detect the revenue label and verify its value
    in the requested fiscal-year column.

    Designed for simple, readable financial statements.
    """
    from column_detector import verify_value_by_year

    label_result = detect_revenue_label(page_text)

    if label_result["status"] != "LABEL_FOUND":
        return {
            "status": "NEEDS_REVIEW",
            "reason": (
                "Revenue row missing or ambiguous."
            ),
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

