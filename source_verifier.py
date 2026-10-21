
import re


def normalise_number(value):
    """Convert a financial number into a comparable format."""
    text = str(value).strip()
    text = text.replace(",", "").replace("$", "")
    text = text.replace("£", "").replace("€", "")
    text = text.replace(" ", "")

    try:
        return float(text)
    except ValueError:
        return None




def extract_numbers(text):
    """Find financial numbers, including comma-separated values."""

    pattern = (
        r"(?<![\w,])"
        r"-?\$?"
        r"(?:\d{1,3}(?:,\d{3})+|\d+)"
        r"(?:\.\d+)?"
        r"(?![\w,]|\.\d)"
    )

    matches = re.findall(pattern, text)

    numbers = []

    for match in matches:
        number = normalise_number(match)

        if number is not None:
            numbers.append(number)

    return numbers




def verify_figure(pages, value, page_number):
    """
    Check whether a figure is present on the cited PDF page.

    Page numbers are 1-based PDF positions, not printed
    page numbers inside the annual report.
    """

    if not isinstance(page_number, int):
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Page number must be an integer.",
        }

    if page_number < 1 or page_number > len(pages):
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Page number is outside the PDF.",
        }

    target = normalise_number(value)

    if target is None:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "The submitted figure is not numeric.",
        }

    page_text = pages[page_number - 1]
    numbers = extract_numbers(page_text)

    if any(abs(number - target) < 0.0001 for number in numbers):
        return {
            "status": "NUMBER_FOUND",
            "reason": (
                f"The number {value} appears on PDF page "
                f"{page_number}."
            ),
        }

    return {
        "status": "NEEDS_REVIEW",
        "reason": (
            f"The number {value} was not found on PDF page "
            f"{page_number}."
        ),
    }


def verify_financial_data(pages, financial_data):
    """
    Check financial figures against their individual PDF pages.

    NUMBER_FOUND means the numeric value appears on the page.
    It does not prove the metric, year or unit is correct.
    """

    if not financial_data:
        return []

    figures = [
        ("Current-year revenue", "revenue_current"),
        ("Previous-year revenue", "revenue_previous"),
        ("Gross profit", "gross_profit"),
        ("Net income", "net_income"),
    ]

    source_pages = financial_data.get("source_pages") or {}

    results = []

    for label, field in figures:
        value = financial_data.get(field)

        # Prefer the figure-specific page reference.
        # Fall back to the previous single-page format.
        page_number = source_pages.get(field)
        if page_number is None:
            page_number = financial_data.get("source_page")

        if value is None or page_number is None:
            result = {
                "status": "NEEDS_REVIEW",
                "reason": "Missing figure or source page.",
            }
        else:
            result = verify_figure(
                pages,
                value,
                page_number,
            )

        results.append({
            "Financial figure": label,
            "Value": value,
            "PDF page": page_number,
            "Result": result["status"],
            "Explanation": result["reason"],
        })

    return results


def extract_evidence_context(
    pages, value, page_number, context_chars=180
):
    """
    Find a financial number on a PDF page and
    return the text surrounding its occurrence.

    This does not verify the metric or fiscal year.
    """

    if not isinstance(page_number, int):
        return None

    if not 1 <= page_number <= len(pages):
        return None

    page_text = pages[page_number - 1]

    pattern = (
        r"(?<![\w,])"
        r"-?\$?"
        r"(?:\d{1,3}(?:,\d{3})+|\d+)"
        r"(?:\.\d+)?"
        r"(?![\w,]|\.\d)"
    )

    target = normalise_number(value)

    if target is None:
        return None

    for match in re.finditer(pattern, page_text):
        number = normalise_number(match.group())

        if number is None:
            continue

        if abs(number - target) < 0.0001:
            start = max(0, match.start() - context_chars)
            end = min(
                len(page_text),
                match.end() + context_chars,
            )

            return {
                "page": page_number,
                "value": value,
                "excerpt": page_text[start:end].strip(),
            }

    return None


def check_financial_label(
    pages, value, page_number, expected_labels
):
    """
    Check whether a financial label appears near a figure.

    This is a preliminary evidence check, not proof
    of the correct metric, year, or accounting units.
    """

    evidence = extract_evidence_context(
        pages,
        value,
        page_number,
    )

    if evidence is None:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Number not found on cited page.",
            "excerpt": None,
        }

    excerpt = evidence["excerpt"].lower()

    for label in expected_labels:
        if label.lower() in excerpt:
            return {
                "status": "LABEL_NEARBY",
                "reason": f"Nearby label found: {label}",
                "excerpt": evidence["excerpt"],
            }

    return {
        "status": "NUMBER_FOUND",
        "reason": "Number found, but expected label not nearby.",
        "excerpt": evidence["excerpt"],
    }

def check_statement_row_and_year(
    pages, value, page_number, row_label,
    fiscal_year, column_index
):
    """
    Check a figure against a financial statement row
    and its expected fiscal-year column.

    column_index starts at 0 for the first year column.
    """

    if not isinstance(page_number, int):
        return {"status": "NEEDS_REVIEW",
                "reason": "Invalid PDF page."}

    if not 1 <= page_number <= len(pages):
        return {"status": "NEEDS_REVIEW",
                "reason": "Page outside PDF."}

    if not isinstance(column_index, int) or column_index < 0:
        return {"status": "NEEDS_REVIEW",
                "reason": "Invalid column index."}

    text = pages[page_number - 1]

    # Look for a year heading in the statement.
    heading = text.split(row_label, 1)[0]

    years = re.findall(r"\b20\d{2}\b", heading)
    distinct_years = list(dict.fromkeys(years))

    # Find the specified financial row.
    matching_rows = [
        line for line in text.splitlines()
        if line.strip().lower().startswith(row_label.lower())
    ]

    if len(matching_rows) != 1:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Expected financial row not uniquely found.",
        }

    row = matching_rows[0]
    values = extract_numbers(row)

    if column_index >= len(values):
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Column index outside extracted values.",
        }

    if column_index >= len(distinct_years):
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Fiscal-year column cannot be established.",
        }

    extracted_year = int(distinct_years[column_index])
    extracted_value = values[column_index]
    target = normalise_number(value)

    if (
        target is not None
        and extracted_year == fiscal_year
        and abs(extracted_value - target) < 0.0001
    ):
        return {
            "status": "ROW_YEAR_MATCH",
            "reason": (
                f"Matched {row_label}: {value} "
                f"in FY{fiscal_year} column."
            ),
            "evidence": row.strip(),
        }

    return {
        "status": "NEEDS_REVIEW",
        "reason": (
            f"Extracted FY{extracted_year}, "
            f"value {extracted_value} "
            f"at column {column_index}."
        ),
        "evidence": row.strip(),
    }


def verify_with_alternative_labels(
    pages, value, page_number, labels,
    fiscal_year, column_index
):
    """
    Verify a financial figure using approved alternative row labels.

    Accept only a unique matching statement row and year.
    Ambiguous or conflicting matches require review.
    """
    matches = []

    for label in labels:
        result = check_statement_row_and_year(
            pages, value, page_number,
            label, fiscal_year, column_index
        )

        if result["status"] == "ROW_YEAR_MATCH":
            matches.append((label, result))

    if len(matches) == 1:
        label, result = matches[0]
        return {
            **result,
            "matched_label": label,
        }

    if len(matches) > 1:
        return {
            "status": "NEEDS_REVIEW",
            "reason": "Multiple alternative labels matched.",
        }

    return {
        "status": "NEEDS_REVIEW",
        "reason": "No approved label matched the figure and fiscal year.",
    }

