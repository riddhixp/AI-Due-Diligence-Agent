
import re


def detect_year_columns(page_text, row_label="Total revenue"):
    """
    Find fiscal-year headings before a financial row.

    Returns the detected years in their extracted order.
    Does not guarantee that headings align with values.
    """

    position = page_text.lower().find(row_label.lower())

    if position == -1:
        return []

    preceding_text = page_text[:position]

    # Restrict the search to the statement heading area.
    heading = preceding_text[:1000]

    years = re.findall(r"\b20\d{2}\b", heading)

    return list(dict.fromkeys(int(year) for year in years))


def verify_value_by_year(
    page_text, row_label, fiscal_year, expected_value
):
    """
    Check a financial figure against its fiscal-year column.
    Intended for simple, clearly extracted PDF tables.
    """
    from source_verifier import extract_numbers, normalise_number

    years = detect_year_columns(page_text, row_label)

    if not years or fiscal_year not in years:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Fiscal year not found in table headings.",
        }

    matching_rows = [
        line for line in page_text.splitlines()
        if line.strip().lower().startswith(row_label.lower())
    ]

    if len(matching_rows) != 1:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Financial row not uniquely identified.",
        }

    row = matching_rows[0]
    values = extract_numbers(row)

    if len(values) != len(years):
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Financial columns could not be aligned.",
        }

    column_index = years.index(fiscal_year)
    actual_value = values[column_index]
    expected = normalise_number(expected_value)

    if expected is not None and abs(actual_value - expected) < 0.0001:
        return {
            "status": "ROW_YEAR_MATCH",
            "reason": f"FY{fiscal_year}: {actual_value:,.0f} matches.",
            "evidence": row.strip(),
        }

    return {
        "status": "NEEDS_REVIEW",
        "reason": (
            f"FY{fiscal_year}: PDF shows {actual_value:,.0f}, "
            f"submitted value is {expected_value}."
        ),
        "evidence": row.strip(),
    }

