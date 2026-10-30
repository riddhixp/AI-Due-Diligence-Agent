"""Prevent empty or cosmetic financial corrections."""


def financial_correction_changes(previous, candidate):
    """Check whether a revised submission changes financial evidence.

    Names, prose or metadata-only edits are deliberately insufficient to
    consume a numerical correction slot. A new source page is material.
    """
    if not previous:
        return True

    fields = (
        "revenue_current", "revenue_previous", "gross_profit", "net_income",
        "operating_income", "operating_cash_flow", "capital_expenditure",
        "subscription_revenue", "operating_cash_flow_previous",
        "operating_cash_flow_two_years_ago",
        "capital_expenditure_previous", "capital_expenditure_two_years_ago",
        "share_repurchases", "stock_based_compensation",
        "deferred_revenue_change", "fiscal_year", "currency", "units",
        "source_page",
    )
    if any(previous.get(field) != candidate.get(field) for field in fields):
        return True
    for field in ("reported", "source_pages"):
        if previous.get(field) != candidate.get(field):
            return True
    return False
