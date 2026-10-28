"""Clear document-bound results and SDK state without changing app preferences."""
DOCUMENT_STATE_KEYS = (
    'file_id', 'report', 'validation', 'financial_data', 'agent_evaluation',
    'report_smoke_test',
    'offline_approval_queue', 'sdk_offline_approval', 'financial_resume_demo',
    'financial_resume_result', 'offline_application_workflow', 'paid_test_plan_preview',
    'offline_practice_suite', 'live_financial_pause', 'live_financial_displayed_request',
    'live_continuation_preflight',
)


def set_active_document(state, document_id):
    """Preserve an unchanged upload; clear transient state on change or removal."""
    if document_id is not None and state.get('file_id') == document_id:
        return False
    had_state = any(key in state for key in DOCUMENT_STATE_KEYS)
    for key in DOCUMENT_STATE_KEYS:
        state.pop(key, None)
    if document_id is not None:
        state['file_id'] = document_id
    return had_state or document_id is not None
