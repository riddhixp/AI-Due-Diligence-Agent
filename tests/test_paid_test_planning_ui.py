import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from scripts.create_conflict_test_fixture import create_conflict_fixture


class PaidTestPlanningUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.pdf_path = create_conflict_fixture(Path(self.folder.name) / 'fixture.pdf')
        self.app = AppTest.from_string(f'''
import streamlit as st
from pathlib import Path
from paid_test_planning_ui import render_paid_test_planning
render_paid_test_planning(st, Path({str(self.pdf_path)!r}).read_bytes())
''')
        block = patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        block.start()
        self.addCleanup(block.stop)
        self.app.run()

    def test_unknown_and_reported_balances_never_enable_paid_execution(self):
        self.app.button(key='prepare_paid_test_plan').click().run()
        self.assertFalse(self.app.exception)
        plan = self.app.session_state['paid_test_plan_preview']['plan']
        self.assertIn('REMAINING_CREDIT_UNKNOWN', plan['blockers'])
        self.app.text_input(key='plan_remaining_usd').set_value('1.00').run()
        self.assertNotIn('paid_test_plan_preview', self.app.session_state)
        self.app.button(key='prepare_paid_test_plan').click().run()
        plan = self.app.session_state['paid_test_plan_preview']['plan']
        self.assertEqual(plan['funding']['remaining_credit_usd_reported'], '1.00')
        self.assertFalse(plan['can_execute'])
        self.assertEqual([button.key for button in self.app.button], ['prepare_paid_test_plan'])

    def test_changed_document_clears_plan(self):
        self.app.button(key='prepare_paid_test_plan').click().run()
        self.pdf_path.write_bytes(self.pdf_path.read_bytes() + b'changed')
        self.app.run()
        self.assertNotIn('paid_test_plan_preview', self.app.session_state)

    def test_invalid_balance_does_not_leave_a_valid_plan(self):
        self.app.text_input(key='plan_remaining_usd').set_value('-1').run()
        self.app.button(key='prepare_paid_test_plan').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.error)
        self.assertNotIn('paid_test_plan_preview', self.app.session_state)
