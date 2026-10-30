
from dataclasses import dataclass
from typing import Optional
from financial_numbers import finite_number, finite_difference, finite_percentage


@dataclass
class ExtendedFinancialData:
    revenue_current: float
    revenue_previous: float
    gross_profit: float
    net_income: float

    operating_income: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    capital_expenditure: Optional[float] = None
    subscription_revenue: Optional[float] = None

    operating_cash_flow_previous: Optional[float] = None
    operating_cash_flow_two_years_ago: Optional[float] = None

    capital_expenditure_previous: Optional[float] = None
    capital_expenditure_two_years_ago: Optional[float] = None

    share_repurchases: Optional[float] = None
    stock_based_compensation: Optional[float] = None
    deferred_revenue_change: Optional[float] = None



def safe_percentage(numerator, denominator):
    """Calculate a finite ratio only for a positive denominator."""
    return finite_percentage(numerator, denominator)


def calculate_financial_insights(data):
    """Calculate diagnostics without inventing missing figures."""

    insights = {
        "revenue_growth": safe_percentage(
            finite_difference(data.revenue_current, data.revenue_previous),
            data.revenue_previous,
        ),
        "gross_margin": safe_percentage(
            data.gross_profit,
            data.revenue_current,
        ),
        "net_margin": safe_percentage(
            data.net_income,
            data.revenue_current,
        ),
        "operating_margin": safe_percentage(
            data.operating_income,
            data.revenue_current,
        ),
        "operating_cash_conversion": safe_percentage(
            data.operating_cash_flow,
            data.net_income,
        ),
        "subscription_revenue_share": safe_percentage(
            data.subscription_revenue,
            data.revenue_current,
        ),
    }

    if (
        finite_number(data.operating_cash_flow)
        and finite_number(data.capital_expenditure)
        and data.capital_expenditure >= 0
    ):
        insights["free_cash_flow"] = finite_difference(
            data.operating_cash_flow, data.capital_expenditure, digits=2,
        )
    else:
        insights["free_cash_flow"] = None

    # Historical free cash flow
    for label, operating_cash_flow, capex in [
        (
            "previous",
            data.operating_cash_flow_previous,
            data.capital_expenditure_previous,
        ),
        (
            "two_years_ago",
            data.operating_cash_flow_two_years_ago,
            data.capital_expenditure_two_years_ago,
        ),
    ]:
        key = f"free_cash_flow_{label}"

        if finite_number(operating_cash_flow) and finite_number(capex) and capex >= 0:
            insights[key] = finite_difference(operating_cash_flow, capex, digits=2)
        else:
            insights[key] = None

    # Check whether shareholder repurchases exceed
    # indicative current-year free cash flow.
    repurchases = data.share_repurchases
    current_fcf = insights["free_cash_flow"]

    if finite_number(repurchases) and repurchases >= 0 and finite_number(current_fcf):
        insights["repurchases_less_free_cash_flow"] = finite_difference(repurchases, current_fcf, digits=2)
    else:
        insights["repurchases_less_free_cash_flow"] = None

    # Non-cash items and cash-flow timing indicators.
    insights["stock_based_compensation"] = (
        data.stock_based_compensation if finite_number(data.stock_based_compensation) else None
    )

    insights["deferred_revenue_change"] = (
        data.deferred_revenue_change if finite_number(data.deferred_revenue_change) else None
    )

    return insights
