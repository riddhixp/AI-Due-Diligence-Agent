"""Streamlit controls for the isolated, zero-credit application rehearsal."""
import math

from investigation_checkpoint import document_fingerprint
from offline_correction_workflow import start_offline_correction_workflow
from financial_approval_resume import decide_and_resume_offline
from financial_approval_preview import financial_approval_preview
from proposed_financial_review_ui import render_proposed_financial_review
from synthetic_conflict_document import read_synthetic_conflict_pages

SESSION_KEY = 'offline_application_workflow'


def render_correction_workflow(st, pdf_bytes):
    st.subheader('FREE application correction workflow')
    st.caption('Scripted offline rehearsal through the application tools. No API credits. '
               'Results stay separate from your real analysis and final report exports.')
    try:
        digest = document_fingerprint(pdf_bytes)
    except (TypeError, ValueError, AttributeError):
        st.error('The rehearsal document is invalid. Upload the synthetic PDF to continue.')
        return
    except Exception:
        st.error('The rehearsal document could not be checked. No workflow was started.')
        return
    session = st.session_state.get(SESSION_KEY)
    if session is not None and (
            not isinstance(session, dict)
            or not isinstance(session.get('document_sha256'), str)
            or not isinstance(session.get('handoff'), dict)
            or not isinstance(session['handoff'].get('status'), str)
            or 'model' not in session):
        st.error('The stored rehearsal is incomplete. Discard it and start a new free rehearsal.')
        _render_discard(st)
        return
    if session is not None and session['document_sha256'] != digest:
        st.session_state.pop(SESSION_KEY, None)
        session = None
    scenarios = {'Standard correction': 'standard',
                 'Recover after unrelated source read': 'source_recovery',
                 'Remove unsupported cash flow': 'optional_removal',
                 'Stop at the request limit': 'request_limit'}
    selected = st.selectbox('Free rehearsal scenario', list(scenarios),
                            key='app_workflow_scenario')
    if st.button('Start FREE application workflow', key='app_workflow_start'):
        try:
            limit_practice = scenarios[selected] == 'request_limit'
            session = start_offline_correction_workflow(
                pdf_bytes, scenario='standard' if limit_practice else scenarios[selected],
                request_limit=5 if limit_practice else 12)
            session['request_limit_practice'] = limit_practice
            session['document_sha256'] = digest
            st.session_state[SESSION_KEY] = session
        except ValueError:
            # Never display raw exception text from PDF parsing or SDK state.
            st.error('Free rehearsal could not start. Check the synthetic PDF and try again.')
        except Exception:
            st.error('Free rehearsal encountered an unexpected error. No workflow was started.')
    if session is None:
        st.caption('Upload synthetic_conflict_test.pdf to rehearse both approval steps.')
        return
    if session.get('request_limit_practice'):
        st.caption('Active rehearsal: request-limit stop. Approve both proposals to see the '
                   'corrected figures retained without a completed review when the five-request '
                   'allowance runs out. This is an expected incomplete result.')
    if session.get('scenario') == 'source_recovery':
        st.caption('Active rehearsal: source-read recovery. The scripted model first reads '
                   'an unrelated page. That correction is blocked; it then reads the cited '
                   'page and requests a new approval. Expect three approval steps.')
    if session.get('scenario') == 'optional_removal':
        st.caption('Active rehearsal: remove unsupported cash flow. The first review flags '
                   'an unsupported optional figure. The correction removes it; unavailable '
                   'cash flow must remain missing, not become zero.')
    budget = getattr(session['model'], 'request_budget', None)
    if budget is not None:
        try:
            usage = budget.snapshot()
            valid = (
                isinstance(usage, dict)
                and all(type(usage.get(key)) is int for key in
                        ('reserved', 'maximum', 'remaining'))
                and usage['maximum'] > 0
                and 0 <= usage['reserved'] <= usage['maximum']
                and usage['remaining'] == usage['maximum'] - usage['reserved']
            )
        except Exception:
            valid = False
        if not valid:
            st.error('The stored rehearsal request counter is invalid. Discard and restart this rehearsal.')
            _render_discard(st)
            return
        st.caption(f"Scripted requests used: {usage['reserved']} of {usage['maximum']}; "
                   f"remaining: {usage['remaining']}. The same allowance covers all approval pauses.")
        st.caption('This is a free rehearsal request limit, not a token or monetary budget.')
    handoff = session['handoff']
    result = session.get('result')
    if result is not None:
        if (handoff.get('status') not in ('COMPLETED_OFFLINE', 'COMPLETED')
                or not isinstance(result, dict)
                or result.get('status') != 'COMPLETED_OFFLINE'
                or session.get('workflow_error') is not None
                or session.get('displayed_request_sha256') is not None
                or result.get('scripted') is not True
                or type(result.get('external_api_calls')) is not int
                or result['external_api_calls'] != 0
                or not isinstance(result.get('evaluation'), dict)
                or result['evaluation'].get('simulation') is not True
                or (result['evaluation'].get('final_eligible') is True
                    and result.get('validation') is not None
                    and not isinstance(result['validation'], dict))
                or (result.get('report') is not None
                    and (not isinstance(result['report'], str)
                         or not result['report'].strip()))
                or not isinstance(result.get('financial'), dict)
                or type(result['financial'].get('revenue_current')) not in (int, float, type(None))
                or (type(result['financial'].get('revenue_current')) is float
                    and not math.isfinite(result['financial']['revenue_current']))
                or (type(result['financial'].get('revenue_current')) in (int, float)
                    and result['financial']['revenue_current'] < 0)
                or (result['evaluation'].get('final_eligible') is True
                    and result['financial'].get('revenue_current') == 0)
                or (result['evaluation'].get('final_eligible') is True
                    and type(result['financial'].get('revenue_current')) not in (int, float))
                or type(result['evaluation'].get('final_eligible')) is not bool
                or (result['evaluation']['final_eligible'] is True
                    and result['evaluation'].get('financial_evidence') != 'PRELIMINARY_CHECKS_PASSED')
                or not isinstance(result['evaluation'].get('financial_evidence'), str)
                or not result['evaluation']['financial_evidence']):
            st.error('The stored rehearsal result is invalid. Discard it and start a new free rehearsal.')
            _render_discard(st)
            return
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
        except ValueError:
            session.pop('displayed_request_sha256', None)
            st.error('Financial approval preview is invalid. Discard and restart the free rehearsal.')
            _render_discard(st)
            return
        except Exception:
            session.pop('displayed_request_sha256', None)
            st.error('Financial approval preview could not be displayed. Discard and restart the free rehearsal.')
            _render_discard(st)
            return
        shown_fingerprint = session.get('displayed_request_sha256')
        st.warning('Financial submission awaiting your decision. Compare the proposed figures with the PDF.')
        st.write('Submission:', preview['metadata'])
        if handoff['checkpoint']['submission_count']:
            st.write('Previously accepted metadata:', preview['previous_metadata'])
        st.dataframe(preview['metrics'], hide_index=True)
        try:
            pages = read_synthetic_conflict_pages(pdf_bytes)
        except Exception:
            session.pop('displayed_request_sha256', None)
            st.error('PDF evidence could not be read. Discard this rehearsal or retry displaying the preview.')
            _render_discard(st)
            return
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
        render_proposed_financial_review(st, handoff['sdk_state'], pages, preview['request_sha256'])
        if handoff['checkpoint']['submission_count']:
            st.write('Previous review:', handoff['checkpoint']['review_status'])
        st.caption('Approving or rejecting continues only the local scripted model. '
                   'Rejecting ends the rehearsal; approving may pause at the next financial request.')
        yes, no = st.columns(2)
        approved = yes.button('Approve and continue FREE workflow', key='app_workflow_approve')
        rejected = no.button('Reject and end FREE workflow', key='app_workflow_reject')
        if approved or rejected:
            try:
                if approved and rejected:
                    raise ValueError('CONFLICTING_APPROVAL_DECISION')
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
                    session.pop('displayed_request_sha256', None)
                st.rerun()
                return  # Never restore the previous approval fingerprint after resuming.
            except ValueError as error:
                if handoff.get('status') != 'AWAITING_APPROVAL':
                    session['workflow_error'] = (
                        'Request allowance exhausted. Progress is retained for inspection; '
                        'the latest figures may be unreviewed. Start a new rehearsal to continue.'
                        if str(error) == 'MODEL_REQUEST_BUDGET_EXHAUSTED' else
                        'Offline continuation failed. Start a new rehearsal to continue.')
                    st.rerun()
                    return  # A failed handoff cannot fall through to the old approval UI.
                st.error('Offline approval could not continue. Check the current request or restart the rehearsal.')
            except Exception:
                if handoff.get('status') == 'AWAITING_APPROVAL':
                    st.error('Offline continuation could not start. No automatic retry was made.')
                else:
                    session['workflow_error'] = 'Offline continuation failed. Start a new rehearsal to continue.'
                    st.rerun()
                    return  # Do not restore a stale fingerprint after a failed handoff.
        session['displayed_request_sha256'] = preview['request_sha256']
    else:
        st.error(session.get('workflow_error',
                            'This rehearsal cannot be resumed again. Start a new rehearsal to continue.'))
        progress = handoff.get('failure_checkpoint')
        if progress is not None:
            if (not isinstance(progress, dict)
                    or type(progress.get('submission_count')) is not int
                    or progress['submission_count'] < 0
                    or not isinstance(progress.get('financial_data'), dict)
                    or (progress.get('review_status') is not None
                        and not isinstance(progress['review_status'], str))):
                st.warning('Saved failure progress is incomplete. Discard this rehearsal to reset it.')
            else:
                st.write('Accepted submissions before failure:', progress['submission_count'])
                st.write('Latest review status:', progress['review_status'] or 'Not completed')
                st.write('Last accepted synthetic revenue:',
                         progress['financial_data'].get('revenue_current', 'Not submitted'))
                st.caption('Read-only progress; accepted figures may still be unverified. '
                           'This failed state cannot be retried or exported as a final report.')
    _render_discard(st)


def _render_discard(st):
    if st.button('Discard FREE application workflow', key='app_workflow_discard'):
        st.session_state.pop(SESSION_KEY, None)
        st.rerun()
