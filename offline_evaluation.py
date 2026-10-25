"""Repeatable full-engine evaluation; synthetic data and scripted model only.

Run with `python -m offline_evaluation`. This never enables a live provider.
"""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile

from financial_approval_resume import decide_and_resume_offline
from final_artifact_policy import final_report_eligible
from offline_correction_workflow import start_offline_correction_workflow
from scripts.create_conflict_test_fixture import create_conflict_fixture


def run_offline_evaluation():
    checks = []
    with tempfile.TemporaryDirectory() as folder:
        pdf = create_conflict_fixture(Path(folder) / 'synthetic.pdf').read_bytes()
    # The engine emits diagnostic tool names; keep CLI output as one JSON object.
    with contextlib.redirect_stdout(StringIO()):
        session = start_offline_correction_workflow(pdf)
        checkpoint = session['handoff']['checkpoint']
        checks.append(('application_reads_source_before_first_pause',
                       checkpoint['tool_calls'] == ['read_page']
                       and checkpoint['submission_count'] == 0
                       and session['model'].calls == 2))
        paused = decide_and_resume_offline(session['handoff'], pdf, True, session['model'])
        handoff = paused['handoff']
        checks.append(('incorrect_revenue_flagged_before_correction',
                       handoff['checkpoint']['financial_data']['revenue_current'] == 130
                       and handoff['checkpoint']['review_status'] == 'NEEDS_REVIEW'))
        checks.append(('source_reread_preserved_at_second_pause',
                       handoff['page_reads'] == 2 and handoff['reads_at_review'] == 1))
        result = decide_and_resume_offline(handoff, pdf, True, session['model'])
        checks.append(('approved_correction_verified',
                       result['financial']['revenue_current'] == 120
                       and result['evaluation']['evaluation'] == 'PRELIMINARY_PASS'
                       and result['evaluation']['final_eligible'] is True))
        checks.append(('scripted_result_excluded_from_final_export',
                       result['evaluation']['simulation'] is True
                       and not final_report_eligible(result['evaluation'])))
        try:
            decide_and_resume_offline(handoff, pdf, True, session['model'])
        except ValueError as error:
            duplicate_blocked = str(error) == 'APPROVAL_RESUME_ALREADY_CLAIMED'
        else:
            duplicate_blocked = False
        checks.append(('duplicate_resume_blocked', duplicate_blocked))
        rejected = start_offline_correction_workflow(pdf)
        pause = decide_and_resume_offline(rejected['handoff'], pdf, True, rejected['model'])
        declined = decide_and_resume_offline(pause['handoff'], pdf, False, rejected['model'])
        checks.append(('declined_correction_keeps_report_incomplete',
                       declined['financial']['revenue_current'] == 130
                       and declined['evaluation']['final_eligible'] is False
                       and declined['validation'] is None))
        # A model can request another submission before reviewing its correction.
        # Preserve that valid pause, then ensure approval cannot bypass tool limits.
        from openai.types.responses import ResponseFunctionToolCall
        from synthetic_financial_fixture import conflict_submission_arguments
        unreviewed = start_offline_correction_workflow(pdf)
        correction_pause = decide_and_resume_offline(unreviewed['handoff'], pdf, True, unreviewed['model'])
        unreviewed['model'].responses.insert(0, [ResponseFunctionToolCall(
            id='extra_eval_f', call_id='extra_eval_c', type='function_call',
            name='submit_financial_data', arguments=json.dumps(
                conflict_submission_arguments(revenue_current=999)), status='completed')])
        extra_pause = decide_and_resume_offline(correction_pause['handoff'], pdf, True, unreviewed['model'])
        saved = extra_pause['handoff']['checkpoint']
        checks.append(('unreviewed_correction_survives_further_pause',
                       saved['submission_count'] == 2 and saved['reviewed_count'] == 1
                       and saved['review_status'] is None
                       and saved['financial_data']['revenue_current'] == 120))
        protected = decide_and_resume_offline(extra_pause['handoff'], pdf, True, unreviewed['model'])
        checks.append(('third_approved_request_cannot_replace_corrected_figures',
                       protected['financial']['revenue_current'] == 120
                       and protected['evaluation']['final_eligible'] is False))
        recovery = start_offline_correction_workflow(pdf, scenario='source_recovery')
        first = decide_and_resume_offline(recovery['handoff'], pdf, True, recovery['model'])
        retry = decide_and_resume_offline(first['handoff'], pdf, True, recovery['model'])
        retained = retry['handoff']['checkpoint']
        checks.append(('refused_correction_preserves_slot_for_source_recovery',
                       retained['submission_count'] == 1 and retained['reviewed_count'] == 1
                       and retained['financial_data']['revenue_current'] == 130
                       and retained['review_status'] == 'NEEDS_REVIEW'
                       and retained['page_read_events'][-1]['page'] == 2))
        recovered = decide_and_resume_offline(retry['handoff'], pdf, True, recovery['model'])
        checks.append(('source_recovery_completes_after_new_approval',
                       recovered['financial']['revenue_current'] == 120
                       and recovered['evaluation']['final_eligible'] is True
                       and not final_report_eligible(recovered['evaluation'])
                       and recovery['model'].calls == 9))
        removal = start_offline_correction_workflow(pdf, scenario='optional_removal')
        removal_pause = decide_and_resume_offline(removal['handoff'], pdf, True, removal['model'])
        before = removal_pause['handoff']['checkpoint']
        checks.append(('unsupported_optional_figure_requires_review',
                       before['financial_data']['operating_cash_flow'] == 999
                       and before['review_status'] == 'NEEDS_REVIEW'))
        removed = decide_and_resume_offline(removal_pause['handoff'], pdf, True, removal['model'])
        checks.append(('approved_optional_removal_clears_value_and_citation',
                       removed['financial']['operating_cash_flow'] is None
                       and removed['financial']['source_pages']['operating_cash_flow'] is None
                       and removed['evaluation']['final_eligible'] is True
                       and not final_report_eligible(removed['evaluation'])))
    return {
        'evaluation': 'PASS' if all(passed for _, passed in checks) else 'FAIL',
        'execution_mode': 'SCRIPTED_OFFLINE_FULL_ENGINE',
        'checks': [{'name': name, 'passed': passed} for name, passed in checks],
        'external_api_calls': 0,
        'autonomous_model_validation': 'NOT_RUN',
        'paid_continuation_enabled': False,
    }


def main():
    try:
        report = run_offline_evaluation()
    except Exception as error:
        report = {'evaluation': 'FAIL', 'execution_mode': 'SCRIPTED_OFFLINE_FULL_ENGINE',
                  'error_type': type(error).__name__, 'autonomous_model_validation': 'NOT_RUN',
                  'paid_continuation_enabled': False}
    print(json.dumps(report, indent=2))
    return 0 if report['evaluation'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
