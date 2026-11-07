"""Real SDK dispatch must not execute a prohibited financial batch."""
import json
import unittest
from unittest.mock import patch
from agents import set_tracing_disabled
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from due_diligence_engine import run_due_diligence
from financial_turn_policy import FinancialTurnHooks
from scripted_offline_model import ScriptedOfflineModel
from synthetic_financial_fixture import PAGES, conflict_submission_arguments


def call(name, arguments, index):
    return ResponseFunctionToolCall(id=f'batch_f{index}', call_id=f'batch_c{index}',
        type='function_call', name=name, arguments=json.dumps(arguments), status='completed')


class FinancialTurnPolicyTests(unittest.TestCase):
    def setUp(self):
        set_tracing_disabled(True)
        network = patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        network.start()
        self.addCleanup(network.stop)

    def test_financial_batches_stop_before_any_tool_executes(self):
        fields = conflict_submission_arguments(source_page=1, revenue_current_page=1,
            revenue_previous_page=1, gross_profit_page=1, net_income_page=1)
        submit = call('submit_financial_data', fields, 1)
        for other in [call('read_page', {'page_number': 1}, 2),
                      call('review_submitted_financials', {}, 3),
                      call('submit_financial_data', fields, 4)]:
            with self.subTest(other=other.name):
                started = []
                class TrackingHooks(FinancialTurnHooks):
                    async def on_tool_start(self, context, agent, tool):
                        started.append(tool.name)
                model = ScriptedOfflineModel()
                model.responses = [[submit, other]]
                with patch('due_diligence_engine.FinancialTurnHooks', return_value=TrackingHooks()):
                    with self.assertRaisesRegex(ValueError, 'FINANCIAL_TOOLS_REQUIRE_SEPARATE_TURNS'):
                        run_due_diligence(PAGES, offline_scripted_model=model)
                self.assertEqual(started, [])
                self.assertEqual(model.calls, 1)

    def test_read_only_batches_remain_available(self):
        model = ScriptedOfflineModel()
        model.responses = [[call('read_page', {'page_number': 1}, 1),
                            call('search_report', {'query': 'Total revenue'}, 2)],
            [ResponseOutputMessage(id='batch_m', type='message', role='assistant', status='completed',
             content=[ResponseOutputText(type='output_text', text='Synthetic reads finished.', annotations=[])])]]
        _, _, financial, evaluation = run_due_diligence(PAGES, offline_scripted_model=model)
        self.assertEqual(model.calls, 2)
        self.assertEqual(financial, {})
        self.assertFalse(evaluation['final_eligible'])
