"""Require model feedback between stateful financial operations."""
from agents import RunHooks


class FinancialTurnHooks(RunHooks):
    async def on_llm_end(self, context, agent, response):
        calls = [item for item in response.output if getattr(item, 'type', None) == 'function_call']
        financial = {'submit_financial_data', 'review_submitted_financials'}
        if len(calls) > 1 and any(getattr(item, 'name', None) in financial for item in calls):
            raise ValueError('FINANCIAL_TOOLS_REQUIRE_SEPARATE_TURNS')
