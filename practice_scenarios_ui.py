"""Run failure rehearsals independently from real analyses and paid-test planning."""
from investigation_checkpoint import document_fingerprint
from practice_scenarios import SCENARIOS, run_practice_suite

PRACTICE_KEY = 'offline_practice_suite'


def render_practice_scenarios(st, pdf_bytes):
    with st.expander('FREE practice: incomplete and unsuccessful investigations'):
        st.caption(f'{len(SCENARIOS)} scripted scenarios exercise the application tools. '
                   'The expected result is an incomplete report when evidence or execution is incomplete. '
                   'This does not test autonomous AI reasoning and uses no API credits.')
        digest = document_fingerprint(pdf_bytes)
        stored = st.session_state.get(PRACTICE_KEY)
        if stored is not None and stored['document_sha256'] != digest:
            st.session_state.pop(PRACTICE_KEY, None)
            stored = None
        if st.button('Run FREE practice suite', key='run_free_practice_suite'):
            try:
                result = run_practice_suite(pdf_bytes)
                stored = {'document_sha256': digest, 'result': result}
                st.session_state[PRACTICE_KEY] = stored
            except ValueError as error:
                st.error(str(error))
            except Exception:
                st.error('Practice run failed unexpectedly. Inspect local tests before continuing.')
        if stored is None:
            return
        result = stored['result']
        if result['evaluation'] == 'PASS':
            st.success(f"All {len(result['scenarios'])} practice scenarios behaved as expected. External API calls: 0.")
        else:
            st.error('A practice scenario did not behave as expected. Review the failed checks.')
        st.dataframe([{'Practice scenario': row['description'],
                       'Observed investigation status': row['observed_status'],
                       'Expected behavior observed': row['expected_behavior_observed']}
                      for row in result['scenarios']], hide_index=True)
        for row in result['scenarios']:
            if not row['expected_behavior_observed']:
                st.write(row['scenario'], row['checks'])
        st.caption('Practice results do not replace your analysis or create a final report download.')
