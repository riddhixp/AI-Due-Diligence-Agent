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

    def test_caught_raw_socket_send_still_fails_acceptance(self):
        original = socket.socket.send

        def attempt():
            try:
                with socket.socket() as client:
                    client.send(b"test")
            except RuntimeError:
                pass
            return {'evaluation': 'PASS', 'external_api_calls': 0,
                    'paid_continuation_enabled': False}

        with patch('offline_evaluation.run_offline_evaluation', side_effect=attempt):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(result['blocked_network_attempts'], 1)
        self.assertIs(socket.socket.send, original)

    def test_caught_socket_sendmsg_attempt_still_fails_acceptance(self):
        original = getattr(socket.socket, 'sendmsg', None)

        def attempt():
            try:
                with socket.socket() as client:
                    client.sendmsg([b"test"])
            except RuntimeError:
                pass
            return {'evaluation': 'PASS', 'external_api_calls': 0,
                    'paid_continuation_enabled': False}

        with patch('offline_evaluation.run_offline_evaluation', side_effect=attempt):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(result['blocked_network_attempts'], 1)
        self.assertIs(getattr(socket.socket, 'sendmsg', None), original)

    def test_swallowed_dns_lookup_still_fails_acceptance(self):
        original = socket.getaddrinfo

        def attempt():
            try:
                socket.getaddrinfo("example.invalid", 443)
            except RuntimeError:
                pass
            return {'evaluation': 'PASS', 'external_api_calls': 0,
                    'paid_continuation_enabled': False}

        with patch('offline_evaluation.run_offline_evaluation', side_effect=attempt):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(result['blocked_network_attempts'], 1)
        self.assertIs(socket.getaddrinfo, original)

    def test_other_socket_paths_are_blocked_and_restored(self):
        operations = (
            ('connect_ex', lambda sock: sock.connect_ex(('127.0.0.1', 9))),
            ('sendall', lambda sock: sock.sendall(b'test')),
            ('sendto', lambda sock: sock.sendto(b'test', ('127.0.0.1', 9))),
        )
        for method, operation in operations:
            with self.subTest(method=method):
                original = getattr(socket.socket, method)

                def attempt():
                    try:
                        with socket.socket() as client:
                            operation(client)
                    except RuntimeError:
                        pass
                    return {'evaluation': 'PASS', 'external_api_calls': 0,
                            'paid_continuation_enabled': False}

                with patch('offline_evaluation.run_offline_evaluation', side_effect=attempt):
                    result = run_acceptance()
                self.assertEqual(result['evaluation'], 'FAIL')
                self.assertEqual(result['blocked_network_attempts'], 1)
                self.assertIs(getattr(socket.socket, method), original)

    def test_practice_suite_network_attempt_invalidates_whole_run(self):
        def attempt(_pdf):
            try:
                socket.getaddrinfo('example.invalid', 443)
            except RuntimeError:
                pass
            return {'evaluation': 'PASS', 'scenarios': [
                {'scenario': 'fake', 'expected_behavior_observed': True}],
                'external_api_calls': 0, 'paid_continuation_enabled': False,
                'autonomous_model_validation': 'NOT_RUN'}

        with patch('practice_scenarios.run_practice_suite', side_effect=attempt):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(result['blocked_network_attempts'], 1)
        self.assertEqual(result['suites']['workflow']['evaluation'], 'PASS')

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

    def test_summary_survives_malformed_suite_rows(self):
        from offline_acceptance import acceptance_summary
        report = {'evaluation': 'FAIL', 'blocked_network_attempts': 0,
                  'suites': {'broken': None, 'partial': {'checks': [None, {'passed': False}]},
                             'invalid': {'evaluation': 'FAIL', 'checks': 'unavailable'}}}
        summary = acceptance_summary(report)
        self.assertIn('broken: FAIL (invalid suite result)', summary)
        self.assertIn('partial: FAIL (0/2 checks)', summary)
        self.assertIn('Failed: invalid check result', summary)
        self.assertIn('invalid: FAIL (0/0 checks)', summary)

    def test_summary_handles_missing_top_level_metadata(self):
        from offline_acceptance import acceptance_summary
        for report in (None, [], {}, {"suites": None}):
            with self.subTest(report=report):
                summary = acceptance_summary(report)
                self.assertIn("Offline acceptance: FAIL", summary)
                self.assertIn("Blocked network attempts: UNKNOWN", summary)
        self.assertIn("invalid suite collection",
                      acceptance_summary({"suites": None}))

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
