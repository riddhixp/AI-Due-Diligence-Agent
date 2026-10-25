import socket
import unittest
from unittest.mock import patch
from offline_acceptance import run_acceptance


class OfflineAcceptanceTests(unittest.TestCase):
    def test_real_scripted_suites_pass_with_network_blocked(self):
        result = run_acceptance()
        self.assertEqual(result['evaluation'], 'PASS')
        self.assertEqual(result['blocked_network_attempts'], 0)
        self.assertEqual(result['autonomous_model_validation'], 'NOT_RUN')

    def test_caught_network_attempt_still_fails_and_guard_is_restored(self):
        original = socket.create_connection
        def attempt():
            try:
                socket.create_connection(('example.invalid', 443))
            except RuntimeError:
                pass
            return {'evaluation': 'PASS', 'external_api_calls': 0,
                    'paid_continuation_enabled': False}
        with patch('offline_evaluation.run_offline_evaluation', side_effect=attempt):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(result['blocked_network_attempts'], 1)
        self.assertIs(socket.create_connection, original)

    def test_errors_are_reported_without_sensitive_messages(self):
        with patch('offline_evaluation.run_offline_evaluation', side_effect=ValueError('secret')):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(result['suites']['workflow']['error_type'], 'ValueError')
        self.assertEqual(result['suites']['failure_practice']['evaluation'], 'PASS')
        self.assertNotIn('secret', str(result))

    def test_summary_names_failed_checks_without_claiming_live_validation(self):
        from offline_acceptance import acceptance_summary
        report = {'evaluation': 'FAIL', 'blocked_network_attempts': 0,
                  'suites': {'workflow': {'evaluation': 'FAIL', 'checks': [
                      {'name': 'reviewed', 'passed': True},
                      {'name': 'citation', 'passed': False}]}}}
        summary = acceptance_summary(report)
        self.assertIn('workflow: FAIL (1/2 checks)', summary)
        self.assertIn('Failed: citation', summary)
        self.assertIn('autonomous model validation NOT_RUN', summary)

    def test_cli_failure_has_nonzero_exit_status(self):
        import contextlib
        import io
        from offline_acceptance import main
        result = {'evaluation': 'FAIL', 'blocked_network_attempts': 1}
        with patch('offline_acceptance.run_acceptance', return_value=result), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--summary']), 1)
        self.assertIn('Offline acceptance: FAIL', output.getvalue())

    def test_cli_default_preserves_machine_readable_json(self):
        import contextlib
        import io
        import json
        from offline_acceptance import main
        result = {'evaluation': 'PASS', 'blocked_network_attempts': 0}
        with patch('offline_acceptance.run_acceptance', return_value=result), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(output.getvalue()), result)

    def test_empty_or_malformed_results_cannot_pass(self):
        from offline_acceptance import _validated_suite
        for result in (None, [], {'evaluation': 'PASS'}, {'checks': []},
                       {'checks': [None]}, {'checks': [{'passed': 1}]}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                _validated_suite(result, 'checks', 'passed')

    def test_contradictory_pass_or_missing_safety_metadata_fails(self):
        from offline_acceptance import _validated_suite
        good = {'evaluation': 'PASS', 'checks': [{'passed': True}],
                'external_api_calls': 0, 'paid_continuation_enabled': False,
                'autonomous_model_validation': 'NOT_RUN'}
        for changed in ({'checks': [{'passed': False}]}, {'external_api_calls': False},
                        {'paid_continuation_enabled': True},
                        {'autonomous_model_validation': None}):
            with self.subTest(changed=changed):
                result = _validated_suite(dict(good, **changed), 'checks', 'passed')
                self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(_validated_suite(good, 'checks', 'passed')['evaluation'], 'PASS')
