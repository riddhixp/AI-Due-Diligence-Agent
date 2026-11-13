import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from scripts.create_conflict_test_fixture import create_conflict_fixture
from practice_scenarios import SCENARIOS


class PracticeUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = create_conflict_fixture(Path(self.folder.name) / 'fixture.pdf')
        self.app = AppTest.from_string(f'''
import streamlit as st
from pathlib import Path
from practice_scenarios_ui import render_practice_scenarios
st.session_state.setdefault('report', 'Original analysis')
render_practice_scenarios(st, Path({str(self.path)!r}).read_bytes())
''', default_timeout=30)
        block = patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        block.start()
        self.addCleanup(block.stop)
        self.app.run()

    def test_practice_suite_does_not_replace_analysis_or_offer_report_export(self):
        self.app.button(key='run_free_practice_suite').click().run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.error)
        result = self.app.session_state['offline_practice_suite']['result']
        self.assertEqual(result['evaluation'], 'PASS')
        self.assertEqual(len(self.app.dataframe[0].value), len(SCENARIOS))
        self.assertEqual(self.app.session_state['report'], 'Original analysis')
        self.assertEqual(len(self.app.get('download_button')), 0)
        self.path.write_bytes(self.path.read_bytes() + b'changed')
        self.app.run()
        self.assertNotIn('offline_practice_suite', self.app.session_state)

    def test_nonfixture_cannot_run_practice(self):
        self.path.write_bytes(b'other file')
        self.app.button(key='run_free_practice_suite').click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.error)
        self.assertNotIn('offline_practice_suite', self.app.session_state)
