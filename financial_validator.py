
from dataclasses import dataclass


@dataclass
class FinancialData:
    company: str
    fiscal_year: int
    currency: str
    units: str
    revenue_current: float
    revenue_previous: float
    gross_profit: float
    net_income: float


def percentage(numerator, denominator):
    if denominator == 0:
        raise ValueError("Denominator cannot be zero")
    return round(numerator / denominator * 100, 2)


def validate_financials(data, reported_metrics):
    calculated = {
        "revenue_growth": percentage(
            data.revenue_current - data.revenue_previous,
            data.revenue_previous,
        ),
        "gross_margin": percentage(
            data.gross_profit,
            data.revenue_current,
        ),
        "net_margin": percentage(
            data.net_income,
            data.revenue_current,
        ),
    }

    results = {}

    for metric, actual in calculated.items():
        reported = reported_metrics.get(metric)

        if reported is None:
            status = "MISSING"
        elif abs(actual - reported) <= 0.05:
            status = "PASS"
        else:
            status = "FAIL"

        results[metric] = {
            "reported": reported,
            "calculated": actual,
            "status": status,
        }

    return results


if __name__ == "__main__":
    # Adobe example taken from our earlier AI report.
    # These figures still require source verification.
    adobe = FinancialData(
        company="Adobe",
        fiscal_year=2025,
        currency="USD",
        units="millions",
        revenue_current=23769,
        revenue_previous=21505,
        gross_profit=21218,
        net_income=7130,
    )

    reported = {
        "revenue_growth": 10.53,
        "gross_margin": 89.27,
        "net_margin": 30.00,
    }

    results = validate_financials(adobe, reported)

    print("\nFINANCIAL ARITHMETIC VALIDATION")
    print(f"Company: {adobe.company}")
    print(f"Fiscal year: {adobe.fiscal_year}\n")

    for name, result in results.items():
        print(
            f"{name}: "
            f"reported={result['reported']}%, "
            f"calculated={result['calculated']}%, "
            f"status={result['status']}"
        )
