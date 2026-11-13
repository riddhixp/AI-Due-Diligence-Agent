"""Free planning controls; this component contains no execution path."""
from investigation_checkpoint import document_fingerprint
from paid_test_planning import prepare_paid_test_plan

PLAN_KEY = 'paid_test_plan_preview'


def render_paid_test_planning(st, pdf_bytes):
    with st.expander('Prepare a paid test — estimate only, no API call'):
        st.caption('Your original £5 includes earlier usage. Planning never adds credit '
                   'or authorizes another paid test.')
        balance = st.text_input('Remaining API credit in USD (optional)', key='plan_remaining_usd',
                                help='Enter the current balance shown in API billing, not the original deposit. '
                                     'Leave blank if unknown. No currency conversion is performed.')
        inputs = (document_fingerprint(pdf_bytes), balance.strip())
        stored = st.session_state.get(PLAN_KEY)
        if stored is not None and stored['inputs'] != inputs:
            st.session_state.pop(PLAN_KEY, None)
            stored = None
        if st.button('Prepare test estimate (FREE)', key='prepare_paid_test_plan'):
            try:
                plan = prepare_paid_test_plan(pdf_bytes, remaining_credit_usd=inputs[1] or None)
                stored = {'inputs': inputs, 'plan': plan}
                st.session_state[PLAN_KEY] = stored
            except ValueError as error:
                st.error(str(error))
        if stored is None:
            return
        plan = stored['plan']
        st.write('Proposed model:', plan['model'])
        st.write('Estimated model-token cost in USD:', plan['cost_estimate_usd'])
        st.write('Proposed planning reserve in USD:', plan['proposed_reserve_usd'])
        st.caption('These estimates assume the planned token and request ceilings. '
                   'They are not an enforced billing cap. Model availability and live '
                   'spend enforcement still require validation.')
        st.write('Planned limits across the entire test:', plan['planned_limits'])
        if 'REMAINING_CREDIT_UNKNOWN' in plan['blockers']:
            st.warning('Current remaining API credit is unknown.')
        if 'INSUFFICIENT_REPORTED_REMAINING_CREDIT' in plan['blockers']:
            st.warning('Reported remaining credit is below the proposed planning reserve.')
        st.info('Planning only. Paid continuation is disabled. Each paid test needs '
                'your separate explicit permission. No API call was made.')
