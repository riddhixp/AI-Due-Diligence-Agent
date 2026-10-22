"""Flag narrative revenue arrows inconsistent with validated chronology."""
import re


def find_reversed_revenue_arrows(report, financial_data):
    if not financial_data:
        return []
    old = financial_data.get("revenue_previous")
    new = financial_data.get("revenue_current")
    if old is None or new is None or old == new:
        return []
    # Matches a compact arrow expression even when prefixed with currency.
    pattern = re.compile(
        r"(?<![\d.])(?:[$£€]\s*)?(\d+(?:\.\d+)?)\s*"
        r"(?:→|->|➜)\s*(?:[$£€]\s*)?(\d+(?:\.\d+)?)"
    )
    issues = []
    for match in pattern.finditer(str(report or "")):
        a, b = map(float, match.groups())
        if abs(a - float(new)) < 0.0001 and abs(b - float(old)) < 0.0001:
            issues.append(
                f"Revenue arrow {match.group(0)!r} reverses the chronology: "
                f"FY previous {old} → current {new}."
            )
    return issues
