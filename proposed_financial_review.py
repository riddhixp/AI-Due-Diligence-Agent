"""Review proposed tool arguments locally without executing or accepting them."""
from agent_financial_review import review_financial_evidence
from financial_approval_preview import pending_financial_request
from optional_financial_validation import validate_optional_financial_data
from optional_statement_metrics import OPTIONAL_STATEMENT_METRICS


def review_proposed_financial_request(state, pages):
    """Return preliminary evidence diagnostics; never mutate the SDK or checkpoint."""
    _, values, fingerprint = pending_financial_request(state)
    metrics = ('revenue_current', 'revenue_previous', 'gross_profit', 'net_income')
    ratios = ('revenue_growth', 'gross_margin', 'net_margin')
    required = ('company', 'fiscal_year', 'currency', 'units', 'source_page',
                *metrics, *(key + '_page' for key in metrics),
                *('reported_' + key for key in ratios))
    if any(key not in values for key in required):
        return {'status': 'REVIEW_UNAVAILABLE', 'request_sha256': fingerprint,
                'reason': 'INCOMPLETE_PROPOSED_FINANCIALS'}
    optional = tuple(item[0] for item in OPTIONAL_STATEMENT_METRICS)
    candidate = {key: values.get(key) for key in
                 ('company', 'fiscal_year', 'currency', 'units', 'source_page', *metrics, *optional)}
    candidate['reported'] = {key: values['reported_' + key] for key in ratios}
    candidate['source_pages'] = {key: values.get(key + '_page') for key in (*metrics, *optional)}
    review = review_financial_evidence(pages, candidate)
    review['optional_issues'] = validate_optional_financial_data(candidate, len(pages))
    review['citation_issues'] = [f'{key}: PDF page {value} is outside the document.'
                                 for key, value in values.items()
                                 if (key == 'source_page' or key.endswith('_page'))
                                 and value is not None and value > len(pages)]
    if review['optional_issues'] or review['citation_issues']:
        review['status'] = 'NEEDS_REVIEW'
    review['request_sha256'] = fingerprint
    return review
