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
    scenarios = {'Standard correction': 'standard',
                 'Recover after unrelated source read': 'source_recovery'}
    selected = st.selectbox('Free rehearsal scenario', list(scenarios),
                            key='app_workflow_scenario')
    if st.button('Start FREE application workflow', key='app_workflow_start'):
        try:
            session = start_offline_correction_workflow(pdf_bytes, scenario=scenarios[selected])
            session['document_sha256'] = digest
            st.session_state[SESSION_KEY] = session
        except ValueError as error:
            st.error(str(error))
    if session is None:
        st.caption('Upload synthetic_conflict_test.pdf to rehearse both approval steps.')
        return
    if session.get('scenario') == 'source_recovery':
        st.caption('Active rehearsal: source-read recovery. The scripted model first reads '
                   'an unrelated page. That correction is blocked; it then reads the cited '
                   'page and requests a new approval. Expect three approval steps.')
    handoff = session['handoff']
    result = session.get('result')
    if result is not None:
        if result['evaluation'].get('final_eligible') is True:
            st.success('Offline workflow completed its scripted checks. External API calls: 0.')
        else:
            st.warning('Offline workflow ended with incomplete checks. External API calls: 0.')
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
            _render_discard(st)
            return
        shown_fingerprint = session.get('displayed_request_sha256', preview['request_sha256'])
        st.warning('Financial submission awaiting your decision. Compare the proposed figures with the PDF.')
        st.write('Submission:', preview['metadata'])
        if handoff['checkpoint']['submission_count']:
            st.write('Previously accepted metadata:', preview['previous_metadata'])
        st.dataframe(preview['metrics'], hide_index=True)
        pages = read_synthetic_conflict_pages(pdf_bytes)
        cited_pages = sorted({page for row in preview['metrics']
                              for page in row['PDF pages'] + row['Previous PDF pages']})
        with st.expander('Source evidence for pending figures'):
            st.caption('Compare the proposed amounts, row labels and fiscal-year columns '
                       'with the proposed and previous PDF citations. Percentages cite their input '
                       'figures; removed values are shown explicitly. The proposal is unverified.')
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
                resumed = decide_and_resume_offline(
                    handoff, pdf_bytes, approved, session['model'],
                    expected_request_sha256=shown_fingerprint,
                    stop_after_rejection=rejected)
                if resumed['status'] == 'AWAITING_APPROVAL':
                    session['handoff'] = resumed['handoff']
                    session.pop('displayed_request_sha256', None)
                else:
                    session['result'] = resumed
                st.rerun()
            except ValueError as error:
                if handoff.get('status') != 'AWAITING_APPROVAL':
                    session['workflow_error'] = 'Offline continuation failed. Start a new rehearsal to continue.'
                    st.rerun()
                st.error(str(error))
            except Exception:
                if handoff.get('status') == 'AWAITING_APPROVAL':
                    st.error('Offline continuation could not start. No automatic retry was made.')
                else:
                    session['workflow_error'] = 'Offline continuation failed. Start a new rehearsal to continue.'
                    st.rerun()
        session['displayed_request_sha256'] = preview['request_sha256']
    else:
        st.error(session.get('workflow_error',
                            'This rehearsal cannot be resumed again. Start a new rehearsal to continue.'))
    _render_discard(st)


def _render_discard(st):
    if st.button('Discard FREE application workflow', key='app_workflow_discard'):
        st.session_state.pop(SESSION_KEY, None)
        st.rerun()
