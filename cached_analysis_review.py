"""Recheck saved figures locally without inventing original SDK tool history."""
from copy import deepcopy
from financial_numbers import finite_number
from optional_statement_metrics import OPTIONAL_STATEMENT_METRICS
from agent_financial_review import review_financial_evidence
from report_verification import finalise_dd_report


def recheck_cached_analysis(saved, pages):
    if (not isinstance(saved, dict)
            or not isinstance(saved.get('report'), str)
            or not saved['report'].strip()):
        raise ValueError('INVALID_SAVED_ANALYSIS')
    raw_financial = saved.get('financial_data', {})
    financial = deepcopy(raw_financial)
    issues = ['ORIGINAL_TOOL_HISTORY_UNAVAILABLE']
    try:
        if not isinstance(financial, dict):
            raise ValueError('INVALID_CACHED_FINANCIALS')
        required = ('revenue_current', 'revenue_previous', 'gross_profit', 'net_income')
        if financial:
            if not all(finite_number(financial.get(key)) for key in required):
                raise ValueError('INVALID_CACHED_FINANCIALS')
            # Dashboard formatting must never depend on coercing cache values.
            year = financial.get('fiscal_year')
            if type(year) is not int or not 1 <= year <= 9999:
                raise ValueError('INVALID_CACHED_FINANCIALS')
            if any(not isinstance(financial.get(key), str)
                   for key in ('company', 'currency', 'units')):
                raise ValueError('INVALID_CACHED_FINANCIALS')
            if any(financial.get(key) is not None and not finite_number(financial[key])
                   for key, *_ in OPTIONAL_STATEMENT_METRICS):
                raise ValueError('INVALID_CACHED_FINANCIALS')
        review = review_financial_evidence(pages, financial)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        financial = {}
        review = {'status': 'REVIEW_UNAVAILABLE', 'arithmetic': {}}
        issues.append('INVALID_CACHED_FINANCIALS')
    if review['status'] != 'PRELIMINARY_CHECKS_PASSED':
        issues.append('FINANCIAL_EVIDENCE_REQUIRES_REVIEW')
    return {
        'report': finalise_dd_report(saved.get('report'), financial, review),
        'validation': review.get('arithmetic') or None,
        'financial_data': financial,
        'agent_evaluation': {
            'evaluation': 'CACHED_ANALYSIS_RECHECK_ONLY',
            'financial_evidence': review['status'],
            'sequence_ok': False, 'issues': issues, 'final_eligible': False,
            'cached_analysis': True, 'source_recheck_attempted': True,
            'source_rechecked': review['status'] != 'REVIEW_UNAVAILABLE',
            'original_tool_history_restored': False, 'api_calls': 0,
        },
    }
