"""Shared read-only proposal diagnostics for live decisions and free rehearsals."""
from proposed_financial_review import review_proposed_financial_request


def render_proposed_financial_review(st, state, pages, expected_fingerprint):
    """Show the preliminary verdict before the collapsed diagnostic details.

    The verdict is read-only: it never approves, executes, or changes a
    pending financial submission. Failures must never look like a pass.
    """
    try:
        review = review_proposed_financial_request(state, pages)
        if review['request_sha256'] != expected_fingerprint:
            raise ValueError('FINANCIAL_APPROVAL_REQUEST_CHANGED')
        status = review['status']
        if type(status) is not str or status not in (
                'PRELIMINARY_CHECKS_PASSED', 'REVIEW_UNAVAILABLE', 'NEEDS_REVIEW'):
            raise ValueError('UNRECOGNIZED_FINANCIAL_REVIEW_STATUS')
        if status == 'PRELIMINARY_CHECKS_PASSED':
            if not _has_complete_passing_evidence(review):
                raise ValueError('UNSUPPORTED_PRELIMINARY_PASS')
            st.info('Proposed figures passed local preliminary checks. They have not been accepted or executed.')
        elif status == 'REVIEW_UNAVAILABLE':
            st.warning('Local checks are unavailable: the proposal is incomplete.')
        else:
            st.warning('Proposed figures need review. Inspect the findings before recording a decision.')
            for finding in _review_attention_summary(review):
                st.caption(finding)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        st.warning('Local checks are unavailable. Inspect the PDF evidence before recording a decision.')
        return

    with st.expander('Local checks of proposed figures'):
        try:
            if review.get('arithmetic'):
                st.write('Arithmetic checks:', review['arithmetic'])
            if review.get('statement_checks'):
                st.dataframe(review['statement_checks'], hide_index=True)
            for issue in (review.get('metadata_issues', []) + review.get('optional_issues', [])
                          + review.get('citation_issues', [])):
                st.warning(issue)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            st.warning('Detailed local checks could not be displayed. Inspect the PDF evidence.')


def _review_attention_summary(review):
    """Count review findings without displaying raw statement or PDF content.

    Only count well-formed results and use generic fixed phrases. The full
    detailed evidence stays in the expandable panel.
    """
    groups = (
        ('arithmetic', 'status', 'PASS', 'Arithmetic discrepancies'),
        ('sources', 'Result', 'NUMBER_FOUND', 'Source-number concerns'),
        ('statement_checks', 'status', 'ROW_YEAR_MATCH', 'Statement row/year concerns'),
    )
    summary = []
    for key, status_key, passing, label in groups:
        rows = review.get(key)
        if key == 'arithmetic' and isinstance(rows, dict):
            rows = list(rows.values())
        if not isinstance(rows, list) or len(rows) > 100:
            continue
        count = sum(isinstance(row, dict) and row.get(status_key) != passing
                    for row in rows)
        if count:
            summary.append(f'{label}: {count}')
    for key, label in (
        ('metadata_issues', 'Financial metadata concerns'),
        ('optional_issues', 'Optional metric concerns'),
        ('citation_issues', 'Citation concerns'),
    ):
        issues = review.get(key)
        if isinstance(issues, list) and 0 < len(issues) <= 100:
            summary.append(f'{label}: {len(issues)}')
    return summary


def _has_complete_passing_evidence(review):
    """Require underlying financial tests to corroborate a preliminary PASS.

    An empty or partial check collection is not proof of success. The underlying
    reviewer owns financial interpretation; this guards presentation only.
    """
    arithmetic = review.get('arithmetic')
    sources = review.get('sources')
    statements = review.get('statement_checks')
    required_arithmetic = {'revenue_growth', 'gross_margin', 'net_margin'}
    required_figures = {'Current-year revenue', 'Previous-year revenue',
                        'Gross profit', 'Net income'}
    if (not isinstance(arithmetic, dict)
            or set(arithmetic) != required_arithmetic
            or not isinstance(sources, list) or not 4 <= len(sources) <= 100
            or not isinstance(statements, list) or not 4 <= len(statements) <= 100):
        return False
    source_labels = [row.get('Financial figure') if isinstance(row, dict) else None
                     for row in sources]
    statement_labels = [row.get('metric') if isinstance(row, dict) else None
                        for row in statements]
    if (len(set(source_labels)) != len(source_labels)
            or not required_figures.issubset(source_labels)
            or len(set(statement_labels)) != len(statement_labels)
            or not required_figures.issubset(statement_labels)):
        return False
    if not all(isinstance(row, dict) and row.get('status') == 'PASS'
               for row in arithmetic.values()):
        return False
    if not all(isinstance(row, dict) and row.get('Result') == 'NUMBER_FOUND'
               for row in sources):
        return False
    if not all(isinstance(row, dict) and row.get('status') == 'ROW_YEAR_MATCH'
               for row in statements):
        return False
    for key in ('metadata_issues', 'optional_issues', 'citation_issues'):
        if review.get(key) != []:
            return False
    return True
