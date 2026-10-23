"""Start a two-approval rehearsal using the actual application's financial tools.

This scripted fixture does not demonstrate autonomous model reasoning. It is
restricted to the project's synthetic conflict PDF and never uses a provider.
"""
import json
from io import BytesIO

from agents import set_tracing_disabled
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from pypdf import PdfReader
from live_financial_pause_handoff import SDKFinancialApprovalPaused
from scripted_offline_model import ScriptedOfflineModel


def start_offline_correction_workflow(pdf_bytes):
    try:
        pages = [page.extract_text() or '' for page in PdfReader(BytesIO(pdf_bytes)).pages]
    except Exception as error:
        raise ValueError('SYNTHETIC_CONFLICT_PDF_REQUIRED') from error
    if (len(pages) != 2
            or 'SYNTHETIC CONFLICT TEST - NOT A REAL COMPANY' not in pages[0]
            or not all(line in pages[1] for line in (
                'Fiscal years 2025 2024 2023', 'Total revenue 120 100 90',
                'Gross profit 80 70 60', 'Net income 30 25 20',
                'The authoritative FY2025 total revenue figure is 120'))):
        raise ValueError('SYNTHETIC_CONFLICT_PDF_REQUIRED')
    fields = dict(company='Illustrative Software Company', fiscal_year=2025,
                  currency='USD', units='millions', revenue_current=120,
                  revenue_previous=100, gross_profit=80, net_income=30,
                  reported_revenue_growth=20, reported_gross_margin=66.67,
                  reported_net_margin=25, source_page=2, revenue_current_page=2,
                  revenue_previous_page=2, gross_profit_page=2, net_income_page=2)
    wrong = dict(fields, revenue_current=130, reported_revenue_growth=30,
                 reported_gross_margin=61.54, reported_net_margin=23.08)

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

    # Start in the same engine used by Streamlit. The page read, first
    # submission request, checkpoint and SDK pause all come from real tools.
    from due_diligence_engine import run_due_diligence
    set_tracing_disabled(True)
    try:
        run_due_diligence(pages, offline_scripted_model=model,
                          financial_approval_required=True, pause_pdf_bytes=pdf_bytes)
    except SDKFinancialApprovalPaused as paused:
        return {'handoff': paused.handoff, 'model': model, 'scripted': True,
                'external_api_calls': 0}
    raise ValueError('EXPECTED_INITIAL_APPROVAL_PAUSE')
