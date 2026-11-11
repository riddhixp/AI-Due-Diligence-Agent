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
        if status == 'PRELIMINARY_CHECKS_PASSED':
            st.info('Proposed figures passed local preliminary checks. They have not been accepted or executed.')
        elif status == 'REVIEW_UNAVAILABLE':
            st.warning('Local checks are unavailable: the proposal is incomplete.')
        else:
            st.warning('Proposed figures need review. Inspect the findings before recording a decision.')
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        st.warning('Local checks are unavailable. Inspect the PDF evidence before recording a decision.')
        return

    with st.expander('Local checks of proposed figures'):
        if review.get('arithmetic'):
            st.write('Arithmetic checks:', review['arithmetic'])
        if review.get('statement_checks'):
            st.dataframe(review['statement_checks'], hide_index=True)
        for issue in (review.get('metadata_issues', []) + review.get('optional_issues', [])
                      + review.get('citation_issues', [])):
            st.warning(issue)
