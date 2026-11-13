"""Conservative row labels for optional financial evidence checks.

Unknown layouts and labels require review rather than a numeric-only match.
Offsets identify the expected fiscal year and column in a descending-year table.
"""
CASH_FLOW_LABELS = (
    'Net cash provided by operating activities',
    'Net cash from operating activities',
    'Net cash used in operating activities',
    'Net cash provided by (used in) operating activities',
    'Operating cash flow',
)
CAPEX_LABELS = (
    'Purchases of property and equipment',
    'Additions to property and equipment',
    'Additions to property, plant and equipment',
    'Capital expenditures',
)
OPTIONAL_STATEMENT_METRICS = (
    ('operating_income', 'Operating income',
     ('Operating income', 'Income from operations', 'Operating profit'), 0),
    ('operating_cash_flow', 'Operating cash flow', CASH_FLOW_LABELS, 0),
    ('operating_cash_flow_previous', 'Previous-year operating cash flow', CASH_FLOW_LABELS, 1),
    ('operating_cash_flow_two_years_ago', 'Operating cash flow two years ago', CASH_FLOW_LABELS, 2),
    ('capital_expenditure', 'Capital expenditure', CAPEX_LABELS, 0),
    ('capital_expenditure_previous', 'Previous-year capital expenditure', CAPEX_LABELS, 1),
    ('capital_expenditure_two_years_ago', 'Capital expenditure two years ago', CAPEX_LABELS, 2),
    ('subscription_revenue', 'Subscription revenue', ('Subscription revenue',), 0),
    ('share_repurchases', 'Share repurchases',
     ('Repurchases of common stock', 'Repurchases of ordinary shares', 'Share repurchases'), 0),
    ('stock_based_compensation', 'Stock-based compensation',
     ('Stock-based compensation', 'Share-based compensation', 'Stock based compensation'), 0),
    ('deferred_revenue_change', 'Change in deferred revenue',
     ('Changes in deferred revenue', 'Change in deferred revenue',
      'Increase in deferred revenue', 'Decrease in deferred revenue'), 0),
)
