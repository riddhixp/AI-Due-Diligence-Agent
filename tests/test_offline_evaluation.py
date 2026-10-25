import unittest
from unittest.mock import patch
from offline_evaluation import run_offline_evaluation


class FullEngineEvaluationTests(unittest.TestCase):
    def test_full_evaluation_runs_with_network_blocked(self):
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            report = run_offline_evaluation()
        self.assertEqual(report['evaluation'], 'PASS')
        self.assertEqual(len(report['checks']), 16)
        self.assertTrue(all(check['passed'] for check in report['checks']))
        self.assertEqual(report['autonomous_model_validation'], 'NOT_RUN')
        self.assertFalse(report['paid_continuation_enabled'])
        self.assertEqual(report['external_api_calls'], 0)
