"""Review and record a genuine paused SDK decision without model continuation."""
from io import BytesIO
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from financial_approval_preview import financial_approval_preview
from proposed_financial_review import review_proposed_financial_request
from investigation_checkpoint import document_fingerprint
from live_financial_approval_decision import decide_live_financial_pause
from tool_state_rebinding import prepare_tool_state

DISPLAY_KEY = 'live_financial_displayed_request'


def render_live_financial_decision(st, handoff, pdf_bytes):
    status = handoff.get('status')
    if status != 'AWAITING_APPROVAL':
        if status in ('APPROVED', 'REJECTED'):
            st.info(f'Financial submission decision recorded: {status}. The model has not resumed.')
        else:
            st.error('This paused decision is unavailable. Discard it before starting a new investigation.')
        return
    try:
        prepare_tool_state(handoff['checkpoint'], pdf_bytes)
        pages = [page.extract_text() or '' for page in PdfReader(BytesIO(pdf_bytes)).pages]
        if not pages or not any(page.strip() for page in pages):
            raise ValueError('READABLE_PDF_REQUIRED')
        preview = financial_approval_preview(handoff)
    except (ValueError, TypeError, KeyError, PdfReadError) as error:
        st.error(f'Approval preview unavailable: {error}')
        return
    digest = document_fingerprint(pdf_bytes)
    displayed = st.session_state.get(DISPLAY_KEY) or {}
    shown = displayed.get('request_sha256') if displayed.get('document_sha256') == digest else None
    st.write('Proposed submission:', preview['metadata'])
    if handoff['checkpoint']['submission_count']:
        st.write('Previously accepted metadata:', preview['previous_metadata'])
    st.dataframe(preview['metrics'], hide_index=True)
    citations = {page for row in preview['metrics']
                 for page in row['PDF pages'] + row['Previous PDF pages']}
    if preview['metadata']['source_page'] is not None:
        citations.add(preview['metadata']['source_page'])
    with st.expander('PDF evidence for paused financial request'):
        st.caption('Compare amounts, units and fiscal-year columns. This preview does not verify the proposal.')
        for page in sorted(citations):
            if type(page) is int and 1 <= page <= len(pages):
                st.markdown(f'**PDF page {page}**')
                st.text(pages[page - 1])
            else:
                st.warning(f'Cited PDF page {page} is unavailable.')
    with st.expander('Local checks of proposed figures'):
        try:
            review = review_proposed_financial_request(handoff['sdk_state'], pages)
            if review['request_sha256'] != preview['request_sha256']:
                raise ValueError('FINANCIAL_APPROVAL_REQUEST_CHANGED')
            if review['status'] == 'PRELIMINARY_CHECKS_PASSED':
                st.info('Proposed figures passed local preliminary checks. They have not been accepted or executed.')
            elif review['status'] == 'REVIEW_UNAVAILABLE':
                st.warning('Local checks are unavailable: the proposal is incomplete.')
            else:
                st.warning('Proposed figures need review. Inspect the findings before recording a decision.')
            if review.get('arithmetic'):
                st.write('Arithmetic checks:', review['arithmetic'])
            if review.get('statement_checks'):
                st.dataframe(review['statement_checks'], hide_index=True)
            for issue in (review.get('metadata_issues', []) + review.get('optional_issues', [])
                          + review.get('citation_issues', [])):
                st.warning(issue)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            st.warning('Local checks are unavailable. Inspect the PDF evidence before recording a decision.')
    st.caption('This records only the paused SDK decision. It does not resume the model or use additional API credits.')
    yes, no = st.columns(2)
    approved = yes.button('Approve paused financial submission', key='live_financial_approve')
    rejected = no.button('Reject paused financial submission', key='live_financial_reject')
    if approved or rejected:
        try:
            if shown != preview['request_sha256']:
                raise ValueError('FINANCIAL_APPROVAL_REQUEST_CHANGED')
            decide_live_financial_pause(handoff, pdf_bytes, approved,
                expected_request_sha256=shown, total_pages=len(pages))
            st.rerun()
        except ValueError as error:
            st.error(str(error))
        except Exception:
            st.error('The SDK decision failed. Discard this paused investigation before continuing.')
    st.session_state[DISPLAY_KEY] = {'document_sha256': digest,
                                  'request_sha256': preview['request_sha256']}
