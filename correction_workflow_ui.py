"""Streamlit controls for the isolated, zero-credit application rehearsal."""
from investigation_checkpoint import document_fingerprint
from offline_correction_workflow import start_offline_correction_workflow
from financial_approval_resume import decide_and_resume_offline
from financial_approval_preview import financial_approval_preview
from synthetic_conflict_document import read_synthetic_conflict_pages

SESSION_KEY = 'offline_application_workflow'


def render_correction_workflow(st, pdf_bytes):
    st.subheader('FREE application correction workflow')
    st.caption('Scripted offline rehearsal through the application tools. No API credits. '
               'Results stay separate from your real analysis and final report exports.')
    digest = document_fingerprint(pdf_bytes)
    session = st.session_state.get(SESSION_KEY)
    if session is not None and session['document_sha256'] != digest:
        st.session_state.pop(SESSION_KEY, None)
        session = None
    if st.button('Start FREE application workflow', key='app_workflow_start'):
        try:
            session = start_offline_correction_workflow(pdf_bytes)
            session['document_sha256'] = digest
            st.session_state[SESSION_KEY] = session
        except ValueError as error:
            st.error(str(error))
    if session is None:
        st.caption('Upload synthetic_conflict_test.pdf to rehearse both approval steps.')
        return
    handoff = session['handoff']
    result = session.get('result')
    if result is not None:
        st.success('Offline workflow finished. External API calls: 0.')
        financial = result['financial']
        st.write('Final synthetic revenue:', financial.get('revenue_current', 'Not submitted'))
        st.write('Evidence check:', result['evaluation']['financial_evidence'])
        st.write('Completion checks passed:', result['evaluation'].get('final_eligible', False))
        st.caption('This scripted result is not a final due diligence report.')
    elif handoff['status'] == 'AWAITING_APPROVAL':
        try:
            preview = financial_approval_preview(handoff)
        except ValueError as error:
            st.error(str(error))
            return
        shown_fingerprint = session.get('displayed_request_sha256', preview['request_sha256'])
        st.warning('Financial submission awaiting your decision. Compare the proposed figures with the PDF.')
        st.write('Submission:', preview['metadata'])
        st.dataframe(preview['metrics'], hide_index=True)
        pages = read_synthetic_conflict_pages(pdf_bytes)
        cited_pages = sorted({row['PDF page'] for row in preview['metrics']
                              if row['PDF page'] is not None})
        with st.expander('Source evidence for pending figures'):
            st.caption('Compare the proposed amounts, row labels and fiscal-year columns '
                       'with the cited PDF text. The proposal has not been verified yet.')
            for page in cited_pages:
                if type(page) in (int, float) and int(page) == page and 1 <= page <= len(pages):
                    st.markdown(f'**PDF page {int(page)}**')
                    st.text(pages[int(page) - 1])
                else:
                    st.warning(f'Cited PDF page {page} is unavailable.')
        if handoff['checkpoint']['submission_count']:
            st.write('Previous review:', handoff['checkpoint']['review_status'])
        st.caption('Approving or rejecting continues only the local scripted model. '
                   'Rejecting ends the rehearsal; approving may pause at the next financial request.')
        yes, no = st.columns(2)
        approved = yes.button('Approve and continue FREE workflow', key='app_workflow_approve')
        rejected = no.button('Reject and end FREE workflow', key='app_workflow_reject')
        if approved or rejected:
            try:
                if shown_fingerprint != preview['request_sha256']:
                    raise ValueError("FINANCIAL_APPROVAL_REQUEST_CHANGED")
                if rejected:
                    # End this fixed demonstration script after a declined request.
                    # The SDK still records rejection and skips the pending tool.
                    session['model'].responses = session['model'].responses[-1:]
                resumed = decide_and_resume_offline(
                    handoff, pdf_bytes, approved, session['model'],
                    expected_request_sha256=shown_fingerprint)
                if resumed['status'] == 'AWAITING_APPROVAL':
                    session['handoff'] = resumed['handoff']
                    session.pop('displayed_request_sha256', None)
                else:
                    session['result'] = resumed
                st.rerun()
            except ValueError as error:
                st.error(str(error))
            except Exception:
                st.error('Offline continuation failed. Start a new rehearsal to continue.')
        session['displayed_request_sha256'] = preview['request_sha256']
    else:
        st.error('This rehearsal cannot be resumed again. Start a new rehearsal to continue.')
    if st.button('Discard FREE application workflow', key='app_workflow_discard'):
        st.session_state.pop(SESSION_KEY, None)
        st.rerun()
