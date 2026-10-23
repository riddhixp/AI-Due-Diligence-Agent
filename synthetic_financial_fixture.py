"""Public synthetic financial data for offline demos; no real company data."""

PAGES = ["""Consolidated Statements of Income
Fiscal years 2025 2024 2023
Total revenue 120 100 90
Gross profit 80 70 60
Net income 30 25 20
"""]


def supported_submission():
    return {
        "company": "Illustrative Software Company",
        "fiscal_year": 2025,
        "currency": "USD",
        "units": "millions",
        "revenue_current": 120,
        "revenue_previous": 100,
        "gross_profit": 80,
        "net_income": 30,
        "reported": {
            "revenue_growth": 20.0,
            "gross_margin": 66.67,
            "net_margin": 25.0,
        },
        "source_pages": {
            "revenue_current": 1,
            "revenue_previous": 1,
            "gross_profit": 1,
            "net_income": 1,
        },
    }


def conflict_submission_arguments(**overrides):
    """Fresh tool arguments for page 2 of the two-page conflict fixture."""
    fields = dict(company='Illustrative Software Company', fiscal_year=2025,
                  currency='USD', units='millions', revenue_current=120,
                  revenue_previous=100, gross_profit=80, net_income=30,
                  reported_revenue_growth=20, reported_gross_margin=66.67,
                  reported_net_margin=25, source_page=2, revenue_current_page=2,
                  revenue_previous_page=2, gross_profit_page=2, net_income_page=2)
    fields.update(overrides)
    return fields
