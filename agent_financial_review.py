
from financial_validator import FinancialData, validate_financials
from optional_statement_metrics import OPTIONAL_STATEMENT_METRICS
from source_verifier import (
    verify_financial_data,
    verify_with_alternative_labels,
)


def review_financial_evidence(pages, submitted):
    """Review financial calculations and cited PDF evidence."""

    if not submitted:
        return {
            "status": "REVIEW_UNAVAILABLE",
            "arithmetic": {},
            "sources": [],
        }

    data = FinancialData(
        company=submitted["company"],
        fiscal_year=submitted["fiscal_year"],
        currency=submitted["currency"],
        units=submitted["units"],
        revenue_current=submitted["revenue_current"],
        revenue_previous=submitted["revenue_previous"],
        gross_profit=submitted["gross_profit"],
        net_income=submitted["net_income"],
    )

    arithmetic = validate_financials(
        data,
        submitted["reported"],
    )

    sources = verify_financial_data(pages, submitted)

    arithmetic_failed = any(
        item["status"] != "PASS"
        for item in arithmetic.values()
    )

    source_failed = any(
        item["Result"] != "NUMBER_FOUND"
        for item in sources
    )


    statement_checks = review_statement_evidence(
        pages, submitted
    )

    statement_failed = any(
        item["status"] != "ROW_YEAR_MATCH"
        for item in statement_checks
    )

    metadata_issues = check_financial_metadata(submitted)


    return {
        "status": (
            "NEEDS_REVIEW"
            if (
                arithmetic_failed
                or source_failed
                or statement_failed
                or metadata_issues
            )
            else "PRELIMINARY_CHECKS_PASSED"
        ),
        "arithmetic": arithmetic,
        "sources": sources,
        "statement_checks": statement_checks,
        "metadata_issues": metadata_issues,
    }


def review_statement_evidence(pages, submitted):
    """Verify supported metrics against financial statement rows."""

    if not submitted:
        return []

    source_pages = submitted.get("source_pages") or {}
    fiscal_year = submitted.get("fiscal_year")

    checks = [
        ("Current-year revenue", "revenue_current",
         ["Total revenue", "Net revenue", "Net sales"],
         fiscal_year, 0),

        ("Previous-year revenue", "revenue_previous",
         ["Total revenue", "Net revenue", "Net sales"],
         fiscal_year - 1 if isinstance(fiscal_year, int) else None, 1),

        ("Gross profit", "gross_profit",
         ["Gross profit", "Gross margin"],
         fiscal_year, 0),

        ("Net income", "net_income",
         ["Net income", "Net earnings"],
         fiscal_year, 0),
    ]

    for field, label, aliases, offset in OPTIONAL_STATEMENT_METRICS:
        # Missing optional metrics remain optional. A supplied value or citation
        # must be established against its own row and period before a pass.
        if submitted.get(field) is None and source_pages.get(field) is None:
            continue
        year = fiscal_year - offset if type(fiscal_year) is int else None
        checks.append((label, field, aliases, year, offset))

    results = []

    for label, field, aliases, year, column in checks:
        value = submitted.get(field)
        page = source_pages.get(field)

        if (
            value is None
            or not isinstance(year, int)
            or isinstance(year, bool)
            or not isinstance(page, int)
            or isinstance(page, bool)
            or not 1 <= page <= len(pages)
        ):
            result = {
                "status": "NEEDS_REVIEW",
                "reason": "Missing or invalid figure, year or page.",
            }
        else:
            result = verify_with_alternative_labels(
                pages=pages,
                value=value,
                page_number=page,
                labels=aliases,
                fiscal_year=year,
                column_index=column,
            )

        results.append({
            "metric": label,
            "status": result["status"],
            "reason": result["reason"],
            "matched_label": result.get("matched_label"),
        })

    return results


def check_financial_metadata(submitted):
    """Identify missing currency and monetary units."""

    issues = []
    unknown_values = {
        "", "unknown", "unspecified",
        "not stated", "not provided", "n/a", "none"
    }

    for field in ("currency", "units"):
        value = str(submitted.get(field) or "").strip().lower()

        if value in unknown_values:
            issues.append(
                f"{field} is not established by the evidence."
            )

    return issues

