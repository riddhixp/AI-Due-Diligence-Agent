"""Evidence-aware financial diligence insights for the AI due diligence app.

This module converts structured financial data into preliminary, decision-focused
findings. Figures and page references are supplied by the extraction workflow;
their presence is not independent source verification.
"""

from financial_insights import ExtendedFinancialData, calculate_financial_insights


def generate_financial_summary(financial_data):
    """Return diligence insight dictionaries compatible with the current dashboard."""

    data = ExtendedFinancialData(
        revenue_current=financial_data["revenue_current"],
        revenue_previous=financial_data["revenue_previous"],
        gross_profit=financial_data["gross_profit"],
        net_income=financial_data["net_income"],
        operating_income=financial_data.get("operating_income"),
        operating_cash_flow=financial_data.get("operating_cash_flow"),
        capital_expenditure=financial_data.get("capital_expenditure"),
        subscription_revenue=financial_data.get("subscription_revenue"),

        operating_cash_flow_previous=financial_data.get(
            "operating_cash_flow_previous"
        ),
        operating_cash_flow_two_years_ago=financial_data.get(
            "operating_cash_flow_two_years_ago"
        ),
        capital_expenditure_previous=financial_data.get(
            "capital_expenditure_previous"
        ),
        capital_expenditure_two_years_ago=financial_data.get(
            "capital_expenditure_two_years_ago"
        ),
        share_repurchases=financial_data.get(
            "share_repurchases"
        ),
        stock_based_compensation=financial_data.get(
            "stock_based_compensation"
        ),
        deferred_revenue_change=financial_data.get(
            "deferred_revenue_change"
        ),

    )
    metrics = calculate_financial_insights(data)
    year = financial_data.get("fiscal_year", "")
    currency = financial_data.get("currency", "")
    units = financial_data.get("units", "")
    unit_label = " ".join(str(x) for x in (currency, units) if x)
    pages = financial_data.get("source_pages") or {}

    def page_for(key):
        # The app has used both source_pages and individual *_page fields.
        # Only display a citation if an actual 1-based page was supplied.
        page = pages.get(key)
        if page is None:
            page = financial_data.get(f"{key}_page")
        return page

    insights = []

    growth = metrics.get("revenue_growth")
    if growth is not None:
        direction = "increased" if growth >= 0 else "declined"
        insights.append({
            "title": (
                f"Revenue {direction} {abs(growth):.2f}%, "
                "but its drivers require validation"
            ),
            "finding": (
                f"Revenue moved from {data.revenue_previous:,.0f} to "
                f"{data.revenue_current:,.0f} {unit_label} in FY{year}. "
                "This is reported growth, not proof of organic growth."
            ),
            "implication": (
                "An investment case that extrapolates this growth could be "
                "overstated if pricing, acquired revenue or temporary demand "
                "accounted for a material share of the increase."
            ),
            "next_step": (
                "Request a two- to three-year revenue bridge by product and "
                "segment, separating pricing, volumes, acquisitions and "
                "other non-recurring effects."
            ),
            "source_pages": [page_for("revenue_current"), page_for("revenue_previous")],
            "priority": "Investment-case validation",
        })

    gross_margin = metrics.get("gross_margin")
    net_margin = metrics.get("net_margin")
    operating_margin = metrics.get("operating_margin")
    if gross_margin is not None and net_margin is not None:
        operating_detail = (
            f" Reported operating margin was {operating_margin:.2f}%."
            if operating_margin is not None else ""
        )
        insights.append({
            "title": (
                f"Gross margin of {gross_margin:.2f}% leaves earnings "
                "quality and cost trends to be tested"
            ),
            "finding": (
                f"FY{year} gross margin was {gross_margin:.2f}% "
                f"and net margin was {net_margin:.2f}%." + operating_detail
            ),
            "implication": (
                "One year's margins do not establish operating leverage, "
                "normalised EBITDA or sustainable profitability. Changes in "
                "expense mix and exceptional items can alter comparability."
            ),
            "next_step": (
                "Compare operating income and expense categories over multiple "
                "periods; reconcile disclosed one-off items and obtain "
                "depreciation/amortisation detail before considering any "
                "normalised EBITDA adjustments."
            ),
            "source_pages": [
                page_for("gross_profit"), page_for("net_income"),
                page_for("operating_income"), page_for("revenue_current"),
            ],
            "priority": "Earnings-quality assessment",
        })

    free_cash_flow = metrics.get("free_cash_flow")
    if free_cash_flow is not None:
        ocf = data.operating_cash_flow
        capex = data.capital_expenditure
        fcf_margin_detail = ""
        if data.revenue_current > 0:
            fcf_margin_detail = (
                f", or {free_cash_flow / data.revenue_current * 100:.2f}% "
                "of reported revenue"
            )
        conversion_detail = ""
        if data.net_income > 0:
            conversion_detail = (
                f" Operating cash flow was {ocf / data.net_income:.2f}x "
                "reported net income."
            )
        insights.append({
            "title": (
                f"Indicative free cash flow of {free_cash_flow:,.0f} "
                f"{unit_label} requires a sustainability bridge"
            ),
            "finding": (
                f"FY{year} operating cash flow of {ocf:,.0f} less cash "
                f"purchases of property and equipment of {capex:,.0f} "
                f"equals {free_cash_flow:,.0f} {unit_label}{fcf_margin_detail}."
                + conversion_detail
            ),
            "implication": (
                "This is an indicative cash-flow measure, not normalised "
                "transaction free cash flow. Working-capital timing, "
                "one-off payments and future investment needs could change "
                "the sustainable amount available to a buyer."
            ),
            "next_step": (
                "Build a multi-year cash-flow bridge covering working capital, "
                "taxes, exceptional items, capital expenditure and planned "
                "technology/cloud investment; reconcile to management's "
                "normalised cash-flow forecast."
            ),
            "source_pages": [
                page_for("operating_cash_flow"),
                page_for("capital_expenditure"),
                page_for("net_income"),
            ],
            "priority": "Cash-flow sustainability",
        })

    subscription_share = metrics.get("subscription_revenue_share")
    if subscription_share is not None:
        insights.append({
            "title": (
                f"Subscription revenue is {subscription_share:.2f}% of sales, "
                "but retention remains unproven"
            ),
            "finding": (
                f"FY{year} subscription revenue was "
                f"{data.subscription_revenue:,.0f} {unit_label}, "
                f"equivalent to {subscription_share:.2f}% of total revenue."
            ),
            "implication": (
                "Subscription mix indicates the business model, not the "
                "quality of renewals. Weak net retention, customer "
                "concentration or price sensitivity could change the "
                "forecast revenue base despite a high subscription share."
            ),
            "next_step": (
                "Obtain renewal and churn cohorts, net revenue retention, "
                "price/volume trends, customer concentration and ARR "
                "reconciliations by major product or segment."
            ),
            "source_pages": [
                page_for("subscription_revenue"),
                page_for("revenue_current"),
            ],
            "priority": "Revenue-quality validation",
        })


    # Highlight missing core analytical metrics without treating
    # business-model-specific optional metrics as universal requirements.
    missing = []

    for metric, label in [
        ("operating_margin", "operating profitability"),
        ("operating_cash_conversion", "cash conversion"),
        ("free_cash_flow", "free cash flow"),
    ]:
        if metrics.get(metric) is None:
            missing.append(label)

    # Subscription revenue share is optional because not every
    # company reports a comparable subscription revenue figure.

    if missing:
        insights.append({
            "title": (
                "Some profitability or cash-flow measures "
                "remain unverified"
            ),
            "finding": (
                "The available structured figures do not support "
                "calculation of: " + ", ".join(missing) + "."
            ),
            "implication": (
                "These missing measures limit parts of the financial "
                "assessment, but do not establish that the original "
                "filing omits the necessary information."
            ),
            "next_step": (
                "Recheck the relevant income and cash-flow statement "
                "pages and extract any available inputs before "
                "requesting additional management information."
            ),
            "source_pages": [],
            "priority": "Financial evidence completion",
        })

    # Add a historical cash-flow and capital-allocation insight
    # when the necessary structured figures are available.
    current_fcf = metrics.get("free_cash_flow")
    previous_fcf = metrics.get("free_cash_flow_previous")
    older_fcf = metrics.get("free_cash_flow_two_years_ago")
    repurchase_gap = metrics.get(
        "repurchases_less_free_cash_flow"
    )

    if (
        current_fcf is not None
        and previous_fcf is not None
        and older_fcf is not None
    ):
        trend = (
            "increased in each of the three reported years"
            if older_fcf < previous_fcf < current_fcf
            else "varied across the three reported years"
        )

        finding = (
            f"Indicative free cash flow {trend}: "
            f"{older_fcf:,.0f}, {previous_fcf:,.0f} and "
            f"{current_fcf:,.0f} {currency} {units}, respectively."
        )

        if repurchase_gap is not None:
            if repurchase_gap > 0:
                finding += (
                    f" Current-year share repurchases exceeded "
                    f"indicative free cash flow by "
                    f"{repurchase_gap:,.0f} {currency} {units}."
                )
            else:
                finding += (
                    " Current-year share repurchases did not "
                    "exceed indicative free cash flow."
                )


        implication = (
            "Historical free cash flow is not necessarily "
            "normalised or sustainable cash generation. "
        )

        if repurchase_gap is None:
            implication += (
                "The relationship between shareholder distributions "
                "and free cash flow cannot be assessed without "
                "complete repurchase information."
            )
        elif repurchase_gap > 0:
            implication += (
                "Share repurchases exceeded indicative free cash "
                "flow, raising questions about financing sources "
                "and capital-allocation flexibility. The difference "
                "does not establish how repurchases were funded."
            )
        else:
            implication += (
                "Share repurchases did not exceed indicative free "
                "cash flow in the current year. However, this "
                "comparison alone does not establish that the "
                "overall capital-allocation policy is sustainable "
                "or that sufficient funds remain for future "
                "investment requirements."
            )

        insights.append({
            "title": (
                "Historical cash generation and capital "
                "allocation require reconciliation"
            ),
            "finding": finding,
            "implication": implication,
            "next_step": (
                "Reconcile three-year operating cash flow, "
                "working capital, non-cash adjustments, "
                "capital expenditure, financing movements "
                "and shareholder distributions."
            ),
            "source_pages": [
                pages.get("operating_cash_flow"),
                pages.get("capital_expenditure"),
                pages.get("operating_cash_flow_previous"),
                pages.get("capital_expenditure_previous"),
                pages.get("operating_cash_flow_two_years_ago"),
                pages.get("capital_expenditure_two_years_ago"),
                pages.get("share_repurchases"),
            ],
            "priority": "Cash-flow and capital allocation",
        })

    for insight in insights:
        insight["source_pages"] = sorted({
            page for page in insight["source_pages"]
            if isinstance(page, int) and not isinstance(page, bool) and page > 0
        })

    return insights
