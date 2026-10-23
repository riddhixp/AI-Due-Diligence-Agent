"""Unpaid full-engine failure rehearsals; expected failures count as safe behavior."""
import argparse
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile

from agents import set_tracing_disabled
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from due_diligence_engine import run_due_diligence
from final_artifact_policy import final_report_eligible
from scripted_offline_model import ScriptedOfflineModel
from synthetic_conflict_document import read_synthetic_conflict_pages
from synthetic_financial_fixture import conflict_submission_arguments

SCENARIOS = {
    'premature_final': 'Model ends before submitting figures',
    'contradictory_narrative': 'Narrative reverses the verified revenue chronology',
    'missing_review': 'Model submits figures but skips review',
    'wrong_year': 'Current and prior-year revenue are swapped',
    'wrong_source_page': 'Figures cite the provisional summary page',
    'unverified_cash_flow': 'Invented operating cash flow must not qualify for verification',
    'cash_flow_wrong_metric': 'A gross-profit number cannot verify operating cash flow',
    'missing_units': 'Monetary units are unspecified',
    'rejected_replacement': 'Invalid correction must preserve previous figures',
    'turn_limit_before_submission': 'Run stops before any financial submission',
    'turn_limit_after_review': 'Run stops after review but before a final response',
}


def _script(name):
    def call(tool, args, index):
        return [ResponseFunctionToolCall(id=f'practice_f{index}', call_id=f'practice_c{index}',
                type='function_call', name=tool, arguments=json.dumps(args), status='completed')]
    final = [ResponseOutputMessage(id='practice_m', type='message', role='assistant',
        status='completed', content=[ResponseOutputText(type='output_text',
        text='Scripted practice result. This narrative cannot establish verification.', annotations=[])])]
    fields = conflict_submission_arguments()
    read = call('read_page', {'page_number': 2}, 1)
    review = call('review_submitted_financials', {}, 3)
    max_turns = 20
    expected_revenue = 120
    if name == 'contradictory_narrative':
        final[0].content[0].text = 'Revenue growth (120 → 100; +20%).'
    if name == 'premature_final':
        return [final], max_turns, None
    if name == 'wrong_year':
        fields.update(revenue_current=100, revenue_previous=120, reported_revenue_growth=-16.67,
                      reported_gross_margin=80, reported_net_margin=30)
        expected_revenue = 100
    if name == 'wrong_source_page':
        fields.update({key: 1 for key in fields if key.endswith('_page')})
        read = call('read_page', {'page_number': 1}, 1)
    if name == 'unverified_cash_flow':
        fields.update(operating_cash_flow=999, operating_cash_flow_page=2)
    if name == 'cash_flow_wrong_metric':
        fields.update(operating_cash_flow=80, operating_cash_flow_page=2)
    if name == 'missing_units':
        fields['units'] = 'unspecified'
    if name == 'rejected_replacement':
        fields.update(revenue_current=130, reported_revenue_growth=30,
                      reported_gross_margin=61.54, reported_net_margin=23.08)
        invalid = conflict_submission_arguments(capital_expenditure=10, capital_expenditure_page=None)
        return [read, call('submit_financial_data', fields, 2), review,
                call('read_page', {'page_number': 2}, 4),
                call('submit_financial_data', invalid, 5),
                call('review_submitted_financials', {}, 6), final], max_turns, 130
    script = [read, call('submit_financial_data', fields, 2), review, final]
    if name == 'missing_review':
        script = [read, call('submit_financial_data', fields, 2), final]
    if name == 'turn_limit_before_submission':
        max_turns, expected_revenue = 1, None
    if name == 'turn_limit_after_review':
        max_turns = 3
    return script, max_turns, expected_revenue


def run_practice_scenario(pdf_bytes, name):
    if name not in SCENARIOS:
        raise ValueError('UNKNOWN_PRACTICE_SCENARIO')
    pages = read_synthetic_conflict_pages(pdf_bytes)
    responses, max_turns, expected_revenue = _script(name)
    model = ScriptedOfflineModel()
    model.responses = responses
    set_tracing_disabled(True)
    report, validation, financial, evaluation = run_due_diligence(
        pages, max_turns=max_turns, offline_scripted_model=model)
    expected_status = ('INTERRUPTED_TURN_LIMIT' if name.startswith('turn_limit_')
                       else 'NEEDS_HUMAN_REVIEW')
    checks = {
        'expected_status': evaluation['evaluation'] == expected_status,
        'figures_preserved': financial.get('revenue_current') == expected_revenue,
        'final_report_blocked': evaluation.get('final_eligible') is False,
        'validation_not_presented_as_complete': validation is None,
        'scripted_output_not_exportable': not final_report_eligible(evaluation),
        'incomplete_report_shown': 'Investigation incomplete' in report,
        'simulation_identified': evaluation.get('simulation') is True,
    }
    return {'scenario': name, 'description': SCENARIOS[name],
            'expected_behavior_observed': all(checks.values()), 'checks': checks,
            'observed_status': evaluation['evaluation'],
            'financial_evidence': evaluation['financial_evidence'],
            'retained_revenue': financial.get('revenue_current'),
            'scripted_model_calls': model.calls, 'external_api_calls': 0}


def run_practice_suite(pdf_bytes):
    results = [run_practice_scenario(pdf_bytes, name) for name in SCENARIOS]
    return {'evaluation': 'PASS' if all(row['expected_behavior_observed'] for row in results) else 'FAIL',
            'execution_mode': 'SCRIPTED_OFFLINE_FAILURE_PRACTICE', 'scenarios': results,
            'external_api_calls': 0, 'autonomous_model_validation': 'NOT_RUN',
            'paid_continuation_enabled': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.pdf is None:
            from scripts.create_conflict_test_fixture import create_conflict_fixture
            with tempfile.TemporaryDirectory() as folder:
                pdf = create_conflict_fixture(Path(folder) / 'synthetic.pdf').read_bytes()
        else:
            pdf = args.pdf.read_bytes()
        with contextlib.redirect_stdout(StringIO()):
            result = run_practice_suite(pdf)
    except Exception as error:
        result = {'evaluation': 'FAIL', 'error_type': type(error).__name__,
                  'execution_mode': 'SCRIPTED_OFFLINE_FAILURE_PRACTICE'}
    print(json.dumps(result, indent=2))
    return 0 if result['evaluation'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
