"""Start a two-approval rehearsal using the actual application's financial tools.

This scripted fixture does not demonstrate autonomous model reasoning. It is
restricted to the project's synthetic conflict PDF and never uses a provider.
"""
import json

from agents import set_tracing_disabled
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from synthetic_conflict_document import read_synthetic_conflict_pages
from live_financial_pause_handoff import SDKFinancialApprovalPaused
from scripted_offline_model import ScriptedOfflineModel
from synthetic_financial_fixture import conflict_submission_arguments


def start_offline_correction_workflow(pdf_bytes, *, scenario="standard"):
    if scenario not in ("standard", "source_recovery", "optional_removal"):
        raise ValueError("UNKNOWN_OFFLINE_WORKFLOW_SCENARIO")
    pages = read_synthetic_conflict_pages(pdf_bytes)
    fields = conflict_submission_arguments()
    wrong = dict(fields, revenue_current=130, reported_revenue_growth=30,
                 reported_gross_margin=61.54, reported_net_margin=23.08)
    if scenario == "optional_removal":
        wrong = dict(fields, operating_cash_flow=999, operating_cash_flow_page=2)

    def call(name, args, index):
        return [ResponseFunctionToolCall(id=f'flow_f{index}', call_id=f'flow_c{index}',
                type='function_call', name=name, arguments=json.dumps(args), status='completed')]

    model = ScriptedOfflineModel()
    model.responses = [
        call('read_page', {'page_number': 2}, 0),
        call('submit_financial_data', wrong, 1),
        call('review_submitted_financials', {}, 2),
        call('read_page', {'page_number': 2}, 3),
        call('submit_financial_data', fields, 4),
        call('review_submitted_financials', {}, 5),
        [ResponseOutputMessage(id='flow_m1', type='message', role='assistant',
            status='completed', content=[ResponseOutputText(type='output_text',
            text='Scripted correction rehearsal completed; human verification required.',
            annotations=[])])],
    ]

    if scenario == "source_recovery":
        # Deliberately visit the wrong page, request a correction that the real
        # application refuses, then read its cited source and request it again.
        model.responses[3] = call('read_page', {'page_number': 1}, 3)
        model.responses[5:5] = [
            call('read_page', {'page_number': 2}, 7),
            call('submit_financial_data', fields, 8),
        ]

    # Start in the same engine used by Streamlit. The page read, first
    # submission request, checkpoint and SDK pause all come from real tools.
    from due_diligence_engine import run_due_diligence
    set_tracing_disabled(True)
    try:
        run_due_diligence(pages, offline_scripted_model=model,
                          financial_approval_required=True, pause_pdf_bytes=pdf_bytes)
    except SDKFinancialApprovalPaused as paused:
        return {'handoff': paused.handoff, 'model': model, 'scripted': True,
                'scenario': scenario,
                'external_api_calls': 0}
    raise ValueError('EXPECTED_INITIAL_APPROVAL_PAUSE')
