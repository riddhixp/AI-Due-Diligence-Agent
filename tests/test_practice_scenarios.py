import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.create_conflict_test_fixture import create_conflict_fixture
from practice_scenarios import SCENARIOS, run_practice_scenario, run_practice_suite


class PracticeScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as folder:
            cls.pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()

    def test_failure_scenarios_with_network_blocked(self):
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            result = run_practice_suite(self.pdf)
        for row in result['scenarios']:
            with self.subTest(scenario=row['scenario']):
                self.assertTrue(row['expected_behavior_observed'], row)
        self.assertEqual(result['evaluation'], 'PASS')
        self.assertEqual(len(result['scenarios']), len(SCENARIOS))
        self.assertFalse(result['paid_continuation_enabled'])

    def test_unrecognized_scenario_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_PRACTICE_SCENARIO'):
            run_practice_scenario(self.pdf, 'paid_model')

    def test_other_document_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SYNTHETIC_CONFLICT_PDF_REQUIRED'):
            run_practice_scenario(b'other report', 'missing_review')
