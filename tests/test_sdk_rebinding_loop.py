"""Restoring an SDK pause must preserve the loop used by synchronous SDK runs."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from financial_approval_resume import decide_and_resume_offline
from offline_correction_workflow import start_offline_correction_workflow
from scripts.create_conflict_test_fixture import create_conflict_fixture
from sdk_state_rebinding import rebind_offline_state


class SDKRebindingLoopTests(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.addCleanup(self.cleanup_loop)
        with tempfile.TemporaryDirectory() as folder:
            self.pdf = create_conflict_fixture(Path(folder) / 'synthetic.pdf').read_bytes()

    def cleanup_loop(self):
        self.loop.close()
        asyncio.set_event_loop(None)

    def test_both_resumes_preserve_the_sdk_default_loop(self):
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            fixture = start_offline_correction_workflow(self.pdf)
            first = decide_and_resume_offline(fixture['handoff'], self.pdf, True, fixture['model'])
            self.assertIs(asyncio.get_event_loop(), self.loop)
            final = decide_and_resume_offline(first['handoff'], self.pdf, True, fixture['model'])
        self.assertIs(asyncio.get_event_loop(), self.loop)
        self.assertFalse(self.loop.is_closed())
        self.assertEqual(final['status'], 'COMPLETED_OFFLINE')
        self.assertEqual(final['financial']['revenue_current'], 120)

    def test_async_context_rejected_without_constructing_restore_coroutine(self):
        fixture = start_offline_correction_workflow(self.pdf)
        state = fixture['handoff']['sdk_state']
        from agents import Agent
        agent = Agent(name='offline', model=fixture['model'])
        async def attempt():
            with patch('sdk_state_rebinding.RunState.from_json') as restore:
                with self.assertRaisesRegex(RuntimeError, 'REQUIRES_SYNC_CONTEXT'):
                    rebind_offline_state(state, agent)
                restore.assert_not_called()
        self.loop.run_until_complete(attempt())
        self.assertIs(asyncio.get_event_loop(), self.loop)

    def test_restore_failure_keeps_original_loop_available(self):
        fixture = start_offline_correction_workflow(self.pdf)
        from agents import Agent
        agent = Agent(name='offline', model=fixture['model'])
        async def failed_restore(*args):
            raise ValueError('RESTORE_FAILED')
        with patch('sdk_state_rebinding.RunState.from_json', side_effect=failed_restore):
            with self.assertRaisesRegex(ValueError, 'RESTORE_FAILED'):
                rebind_offline_state(fixture['handoff']['sdk_state'], agent)
        self.assertIs(asyncio.get_event_loop(), self.loop)
        self.assertFalse(self.loop.is_closed())
