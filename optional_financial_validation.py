from financial_numbers import finite_number
from optional_statement_metrics import OPTIONAL_STATEMENT_METRICS

OPTIONAL_METRICS = tuple(item[0] for item in OPTIONAL_STATEMENT_METRICS)


def validate_optional_financial_data(data, total_pages):
    """Validate optional values and their PDF source pages.

    Returns a list of problems. An empty list means that
    the supplied value/page pairs are structurally valid.
    It does not establish source accuracy.
    """

    issues = []
    source_pages = data.get("source_pages") or {}

    for metric in OPTIONAL_METRICS:
        value = data.get(metric)
        page = source_pages.get(metric)

        if value is None and page is None:
            continue

        if value is None or page is None:
            issues.append(
                f"{metric}: value and source page must "
                "both be provided, or both be missing."
            )
            continue

        if isinstance(page, bool) or not isinstance(page, int):
            issues.append(
                f"{metric}: PDF page must be an integer."
            )
        elif not 1 <= page <= total_pages:
            issues.append(
                f"{metric}: PDF page {page} is outside "
                f"the document's {total_pages} pages."
            )

        if not finite_number(value):
            issues.append(
                f"{metric}: financial value must be a finite number."
            )

    return issues
