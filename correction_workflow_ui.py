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
                or (result.get('validation') is not None
                    and not isinstance(result['validation'], dict))
                or (result.get('report') is not None
                    and (not isinstance(result['report'], str)
                         or not result['report'].strip()))
                or not isinstance(result.get('financial'), dict)
                or any(type(value) is float and not math.isfinite(value)
                       for value in result['financial'].values())
                or any(type(value) is bool
                       for value in result['financial'].values())
                or any(isinstance(value, str) and not value.strip()
                       for value in result['financial'].values())
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
                or not _valid_evidence_status(result['evaluation'].get('financial_evidence'))):
            st.error('The stored rehearsal result is invalid. Discard it and start a new free rehearsal.')
            _render_discard(st)
            return
        st.info('Rehearsal finished. Review the scripted outcome below; it is not a final report.')
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
        try:
            checkpoint = handoff.get('checkpoint')
            if (not isinstance(checkpoint, dict)
                    or type(checkpoint.get('submission_count')) is not int
                    or not 0 <= checkpoint['submission_count'] <= 10000
                    or not isinstance(preview, dict)
                    or not _valid_approval_fingerprint(preview.get('request_sha256'))
                    or not _valid_preview_metadata(preview.get('metadata'))
                    or (checkpoint['submission_count'] > 0
                        and not _valid_preview_metadata(preview.get('previous_metadata')))):
                raise ValueError('INVALID_APPROVAL_PREVIEW')
            cited_pages = _validated_cited_pages(
                preview['metrics'], preview['metadata'], preview.get('previous_metadata'))
        except (TypeError, ValueError, KeyError):
            session.pop('displayed_request_sha256', None)
            st.error('Financial approval preview data is invalid. Discard and restart the free rehearsal.')
            _render_discard(st)
            return
        shown_fingerprint = session.get('displayed_request_sha256')
        if (shown_fingerprint is not None
                and not _valid_approval_fingerprint(shown_fingerprint)):
            session.pop('displayed_request_sha256', None)
            shown_fingerprint = None  # An invalid receipt cannot authorize a click.
        try:
            pages = read_synthetic_conflict_pages(pdf_bytes)
            if not _valid_offline_evidence_pages(pages):
                raise ValueError('INVALID_OFFLINE_EVIDENCE_PAGES')
        except Exception:
            session.pop('displayed_request_sha256', None)
            st.error('PDF evidence could not be read. Discard this rehearsal or retry displaying the preview.')
            _render_discard(st)
            return
        st.info('Reviewer action needed: compare proposed figures against their cited PDF pages.')
        st.caption(_approval_step_summary(checkpoint['submission_count']))
        # The fixture deliberately starts with a false provisional headline.
        # Explain the exercise before users reach the approval controls.
        guidance = _scripted_decision_guidance(
            session.get('scenario'), checkpoint['submission_count'],
            preview['metrics'])
        if guidance:
            st.warning(guidance)
        missing_pages = [page for page in cited_pages if page > len(pages)]
        if missing_pages:
            st.warning('One or more cited PDF pages are unavailable. Approval will be refused; '
                       'you can reject this proposal or restart the free rehearsal.')
        elif cited_pages:
            st.caption(f'PDF evidence available for {len(cited_pages)} cited page(s). '
                       'Availability does not establish that financial figures are correct.')
        st.warning('Financial submission awaiting your decision. Compare the proposed figures with the PDF.')
        st.write('Submission:', preview['metadata'])
        if handoff['checkpoint']['submission_count']:
            st.write('Previously accepted metadata:', preview['previous_metadata'])
        st.dataframe(preview['metrics'], hide_index=True)
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
        st.info('Rehearsal stopped. Inspect read-only progress or start a new free rehearsal.')
        # Session state is not a trusted source for user-visible exception text.
        # Only the application's known, sanitized failure messages may be shown.
        safe_failure_messages = (
            'Request allowance exhausted. Progress is retained for inspection; '
            'the latest figures may be unreviewed. Start a new rehearsal to continue.',
            'Offline continuation failed. Start a new rehearsal to continue.',
        )
        failure_message = session.get('workflow_error')
        st.error(failure_message if failure_message in safe_failure_messages
                 else 'This rehearsal cannot be resumed again. Start a new rehearsal to continue.')
        progress = handoff.get('failure_checkpoint')
        if progress is not None:
            if not _valid_failure_progress(progress):
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


def _validated_cited_pages(metrics, metadata=None, previous_metadata=None):
    """Only allow integer PDF citations from well-formed preview rows.

    An unavailable (out-of-range) positive page can still be shown as a warning.
    Unknown types must never reach sorting, display or financial approval.
    """
    # The rehearsal has only a small number of metrics. Reject malformed or
    # oversized saved previews rather than rendering unbounded evidence text.
    if not isinstance(metrics, list) or len(metrics) > 100:
        raise ValueError('INVALID_PREVIEW_METRICS')
    pages = set()
    for row in metrics:
        if not isinstance(row, dict):
            raise ValueError('INVALID_PREVIEW_ROW')
        if not _valid_preview_metric_row(row):
            raise ValueError('INVALID_PREVIEW_ROW_VALUE')
        for field in ('PDF pages', 'Previous PDF pages'):
            citations = row.get(field)
            if not isinstance(citations, list) or len(citations) > 128:
                raise ValueError('INVALID_PREVIEW_CITATIONS')
            for page in citations:
                if type(page) is not int or page < 1:
                    raise ValueError('INVALID_PREVIEW_CITATION_PAGE')
                pages.add(page)
                if len(pages) > 128:
                    raise ValueError('TOO_MANY_PREVIEW_CITATIONS')
    # The primary source page may differ from each metric's citation.
    # Display it alongside metric evidence so conflicting figures are visible.
    for source in (metadata, previous_metadata):
        if source is None:
            continue
        if not _valid_preview_metadata(source):
            raise ValueError('INVALID_PREVIEW_SOURCE_METADATA')
        page = source.get('source_page')
        if page is not None:
            if type(page) is not int or page < 1:
                raise ValueError('INVALID_PREVIEW_SOURCE_PAGE')
            pages.add(page)
    if len(pages) > 128:
        raise ValueError('TOO_MANY_PREVIEW_CITATIONS')
    return sorted(pages)


def _valid_preview_metadata(metadata):
    """Permit only concise display-safe scalar metadata from a stored preview."""
    if not isinstance(metadata, dict) or len(metadata) > 16:
        return False
    for key, value in metadata.items():
        if not isinstance(key, str) or not key or len(key) > 64:
            return False
        if value is None:
            continue
        if type(value) is int:
            continue
        if (not isinstance(value, str) or len(value) > 256
                or any(ord(char) < 32 or ord(char) == 127 for char in value)):
            return False
    return True


def _valid_approval_fingerprint(value):
    """Accept only bounded, printable receipt tokens; never arbitrary session text."""
    return (isinstance(value, str) and 1 <= len(value) <= 128
            and all(char.isascii() and (char.isalnum() or char in '-_') for char in value))


def _valid_preview_metric_row(row):
    """Avoid sending unexpected objects or nonfinite financial values to Streamlit."""
    allowed = {'Metric', 'Previous', 'Proposed', 'PDF page', 'PDF pages',
               'Previous PDF pages', 'Change', 'Evidence'}
    if not set(row).issubset(allowed):
        return False
    for field in ('Metric', 'Change', 'Evidence'):
        value = row.get(field)
        if value is not None and (not isinstance(value, str)
                                  or len(value) > 256
                                  or any(ord(char) < 32 or ord(char) == 127
                                         for char in value)):
            return False
    for field in ('Previous', 'Proposed'):
        value = row.get(field)
        if value is not None and (type(value) not in (int, float)
                                  or not math.isfinite(value)):
            return False
    page = row.get('PDF page')
    return page is None or (type(page) is int and page >= 1)


def _valid_failure_progress(progress):
    """Check saved failure-state figures before showing them in the read-only UI."""
    if not isinstance(progress, dict):
        return False
    count = progress.get('submission_count')
    data = progress.get('financial_data')
    status = progress.get('review_status')
    if type(count) is not int or not 0 <= count <= 10000:
        return False
    if not isinstance(data, dict):
        return False
    revenue = data.get('revenue_current')
    # A financial figure cannot be described as accepted before any submission.
    if count == 0 and revenue is not None:
        return False
    if revenue is not None and (type(revenue) not in (int, float)
                                or not math.isfinite(revenue) or revenue < 0):
        return False
    if status is not None and (not isinstance(status, str)
                               or len(status) > 128
                               or any(ord(char) < 32 or ord(char) == 127
                                      for char in status)):
        return False
    return True


def _valid_offline_evidence_pages(pages):
    """Restrict offline evidence display to readable, bounded PDF page text."""
    return (isinstance(pages, (list, tuple))
            and 1 <= len(pages) <= 100
            and all(type(page) is str and 0 < len(page.strip()) <= 100000
                    and len(page) <= 100000 for page in pages))


def _valid_evidence_status(value):
    """Use only statuses produced by the deterministic financial reviewer."""
    return type(value) is str and value in (
        'REVIEW_UNAVAILABLE', 'NEEDS_REVIEW', 'PRELIMINARY_CHECKS_PASSED',
    )


def _approval_step_summary(accepted_count):
    """Explain the decision sequence without implying financial verification."""
    if type(accepted_count) is not int or not 0 <= accepted_count <= 10000:
        raise ValueError('INVALID_APPROVAL_STEP')
    if accepted_count == 0:
        return ('Approval step 1: no financial submission has been accepted yet. '
                'The proposed figures are unverified.')
    return (f'Approval step {accepted_count + 1}: {accepted_count} earlier '
            f'financial submission(s) accepted for the scripted rehearsal. '
            'Acceptance does not mean the figures passed evidence review.')


def _scripted_decision_guidance(scenario, accepted_count, metrics):
    """Explain a synthetic test decision without endorsing unsupported approval."""
    if scenario not in ('standard', 'source_recovery', 'optional_removal'):
        return None
    if type(accepted_count) is not int or accepted_count < 0:
        return None
    if not isinstance(metrics, list):
        return None
    revenue_rows = [row for row in metrics if isinstance(row, dict)
                    and row.get('Metric') == 'Revenue current']
    if len(revenue_rows) != 1:
        return None
    proposed = revenue_rows[0].get('Proposed')
    if type(proposed) not in (int, float):
        return None
    if proposed == 130 and accepted_count == 0:
        return ('Synthetic test: USD 130 million is the misleading provisional '
                'headline. The authoritative statement on PDF page 2 shows '
                'USD 120 million. Approving this incorrect proposal is ONLY '
                'a deliberate exercise of the correction controls, not a '
                'recommended decision for real financial due diligence.')
    if proposed == 120 and accepted_count > 0:
        return ('Synthetic correction: the proposed USD 120 million now matches '
                'the authoritative statement on PDF page 2. Compare the local '
                'financial checks before approving; an earlier acceptance '
                'did not establish that the figures were verified.')
    if scenario == 'optional_removal' and accepted_count == 0:
        return ('Synthetic optional-metric exercise: review the unsupported '
                'cash-flow amount and its source citation. The next proposal '
                'removes unsupported data rather than replacing it with zero.')
    return None
