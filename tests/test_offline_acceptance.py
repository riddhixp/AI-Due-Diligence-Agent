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

    def test_acceptance_summary_lists_both_offline_suites(self):
        from offline_acceptance import acceptance_summary
        # The real suite is exercised once above and again by the CI acceptance step.
        # Check the presentation contract without rerunning expensive investigations.
        result = {'evaluation': 'PASS', 'blocked_network_attempts': 0,
                  'suites': {'workflow': {'evaluation': 'PASS', 'checks': [{'passed': True}]},
                             'failure_practice': {'evaluation': 'PASS',
                                                  'scenarios': [{'expected_behavior_observed': True}]}}}
        summary = acceptance_summary(result)
        self.assertEqual(result['evaluation'], 'PASS')
        self.assertIn('Offline acceptance: PASS', summary)
        self.assertIn('workflow: PASS', summary)
        self.assertIn('failure_practice: PASS', summary)
        self.assertIn('Blocked network attempts: 0', summary)
        self.assertIn('autonomous model validation NOT_RUN', summary)

    def test_cli_json_and_summary_exit_success_without_paid_calls(self):
        import contextlib
        import io
        import json
        from offline_acceptance import main

        verified_report = {'evaluation': 'PASS', 'blocked_network_attempts': 0,
                           'paid_continuation_enabled': False,
                           'autonomous_model_validation': 'NOT_RUN'}
        for args in ([], ['--summary']):
            with self.subTest(args=args), patch('offline_acceptance.run_acceptance',
                    return_value=verified_report), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(args), 0)
            if args:
                self.assertIn('Offline acceptance: PASS', output.getvalue())
                self.assertIn('Blocked network attempts: 0', output.getvalue())
            else:
                report = json.loads(output.getvalue())
                self.assertEqual(report['evaluation'], 'PASS')
                self.assertEqual(report['blocked_network_attempts'], 0)
                self.assertIs(report['paid_continuation_enabled'], False)
                self.assertEqual(report['autonomous_model_validation'], 'NOT_RUN')

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

    def test_suite_validation_omits_unexpected_sensitive_metadata(self):
        from offline_acceptance import _validated_suite
        result = {'evaluation': 'PASS', 'checks': [{'name': 'demo', 'passed': True}],
                  'external_api_calls': 0, 'paid_continuation_enabled': False,
                  'autonomous_model_validation': 'NOT_RUN',
                  'raw_pdf_text': 'CONFIDENTIAL_DOCUMENT_MARKER',
                  'debug_error': 'API_KEY_MARKER'}
        validated = _validated_suite(result, 'checks', 'passed')
        self.assertEqual(validated['evaluation'], 'PASS')
        self.assertNotIn('raw_pdf_text', validated)
        self.assertNotIn('debug_error', validated)
        self.assertNotIn('CONFIDENTIAL_DOCUMENT_MARKER', str(validated))
        self.assertNotIn('API_KEY_MARKER', str(validated))

    def test_suite_rows_exclude_sensitive_details_and_unsafe_labels(self):
        from offline_acceptance import _validated_suite
        result = {'evaluation': 'PASS',
                  'checks': [{'name': 'SAFE_CHECK', 'passed': True,
                              'pdf_text': 'PRIVATE_PDF_MARKER'},
                             {'name': 'SECRET:token=abc', 'passed': True,
                              'debug': 'SECRET_DEBUG_MARKER'}],
                  'external_api_calls': 0, 'paid_continuation_enabled': False,
                  'autonomous_model_validation': 'NOT_RUN'}
        validated = _validated_suite(result, 'checks', 'passed')
        self.assertEqual(validated['evaluation'], 'PASS')
        self.assertEqual(validated['checks'],
                         [{'name': 'SAFE_CHECK', 'passed': True},
                          {'name': 'unnamed', 'passed': True}])
        for marker in ('PRIVATE_PDF_MARKER', 'SECRET_DEBUG_MARKER', 'token=abc'):
            self.assertNotIn(marker, str(validated))

    def test_practice_scenario_rows_preserve_outcomes_without_details(self):
        from offline_acceptance import _validated_suite
        data = {'evaluation': 'FAIL', 'scenarios': [
            {'scenario': 'wrong_year', 'expected_behavior_observed': False,
             'description': 'CONFIDENTIAL_SCENARIO_DETAIL', 'financial_data': {'revenue': 999}}],
            'external_api_calls': 0, 'paid_continuation_enabled': False,
            'autonomous_model_validation': 'NOT_RUN'}
        result = _validated_suite(data, 'scenarios', 'expected_behavior_observed')
        self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(result['scenarios'], [
            {'scenario': 'wrong_year', 'expected_behavior_observed': False}])
        self.assertNotIn('CONFIDENTIAL_SCENARIO_DETAIL', str(result))

    def test_rejects_nonboolean_failure_practice_result_even_if_suite_claims_pass(self):
        from offline_acceptance import _validated_suite
        baseline = {'evaluation': 'PASS', 'scenarios': [
            {'scenario': 'wrong_year', 'expected_behavior_observed': True}],
            'external_api_calls': 0, 'paid_continuation_enabled': False,
            'autonomous_model_validation': 'NOT_RUN'}
        for wrong in (1, 'true', None, []):
            with self.subTest(wrong=wrong):
                altered = dict(baseline, scenarios=[
                    {'scenario': 'wrong_year', 'expected_behavior_observed': wrong}])
                with self.assertRaisesRegex(ValueError, 'INVALID_SUITE_CHECKS'):
                    _validated_suite(altered, 'scenarios', 'expected_behavior_observed')
        self.assertEqual(_validated_suite(baseline, 'scenarios',
                         'expected_behavior_observed')['evaluation'], 'PASS')

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
