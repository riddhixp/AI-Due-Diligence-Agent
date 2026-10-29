import socket
import unittest
from unittest.mock import patch
from offline_acceptance import run_acceptance


class OfflineAcceptanceTests(unittest.TestCase):
    def setUp(self):
        # Keep unit tests fast and deterministic. Real integration suites run
        # separately in the offline-integration and network-acceptance CI jobs.
        workflow = {'evaluation': 'PASS', 'checks': [{'name': 'fixture', 'passed': True}],
                    'external_api_calls': 0, 'paid_continuation_enabled': False,
                    'autonomous_model_validation': 'NOT_RUN'}
        practice = {'evaluation': 'PASS', 'scenarios': [
            {'scenario': 'fixture', 'expected_behavior_observed': True}],
            'external_api_calls': 0, 'paid_continuation_enabled': False,
            'autonomous_model_validation': 'NOT_RUN'}
        for target, result in (
                ('offline_evaluation.run_offline_evaluation', workflow),
                ('practice_scenarios.run_practice_suite', practice)):
            fixture = patch(target, return_value=result)
            fixture.start()
            self.addCleanup(fixture.stop)

    def test_acceptance_summary_lists_both_offline_suites(self):
        from offline_acceptance import acceptance_summary
        # Real suites run in separate CI integration and acceptance jobs.
        # Check the presentation contract without rerunning expensive investigations.
        result = {'evaluation': 'PASS', 'blocked_network_attempts': 0,
                  'suites': {'workflow': {'evaluation': 'PASS', 'checks': [{'passed': True}],
                                          'external_api_calls': 0, 'paid_continuation_enabled': False,
                                          'autonomous_model_validation': 'NOT_RUN'},
                             'failure_practice': {'evaluation': 'PASS',
                                                  'scenarios': [{'expected_behavior_observed': True}],
                                                  'external_api_calls': 0, 'paid_continuation_enabled': False,
                                                  'autonomous_model_validation': 'NOT_RUN'}}}
        summary = acceptance_summary(result)
        self.assertEqual(result['evaluation'], 'PASS')
        self.assertIn('Offline acceptance: PASS', summary)
        self.assertIn('workflow: PASS', summary)
        self.assertIn('failure_practice: PASS', summary)
        self.assertIn('Blocked network attempts: 0', summary)
        self.assertIn('autonomous model validation NOT_RUN', summary)

    def test_summary_refuses_unsubstantiated_top_level_pass(self):
        from offline_acceptance import acceptance_summary
        for report in (
                {'evaluation': 'PASS', 'blocked_network_attempts': 0},
                {'evaluation': 'PASS', 'blocked_network_attempts': 0, 'suites': {}},
                {'evaluation': 'PASS', 'blocked_network_attempts': 1, 'suites': {}},
                {'evaluation': 'PASS', 'blocked_network_attempts': 0,
                 'suites': {'workflow': {'evaluation': 'PASS'}, 'failure_practice': {'evaluation': 'PASS'}}}):
            with self.subTest(report=report):
                self.assertIn('Offline acceptance: FAIL', acceptance_summary(report))

    def test_cli_json_and_summary_exit_success_without_paid_calls(self):
        import contextlib
        import io
        import json
        from offline_acceptance import main

        verified_report = {'evaluation': 'PASS', 'blocked_network_attempts': 0,
                           'paid_continuation_enabled': False,
                           'autonomous_model_validation': 'NOT_RUN',
                           'suites': {
                               'workflow': {'evaluation': 'PASS',
                                            'checks': [{'name': 'test', 'passed': True}],
                                            'external_api_calls': 0,
                                            'paid_continuation_enabled': False,
                                            'autonomous_model_validation': 'NOT_RUN'},
                               'failure_practice': {'evaluation': 'PASS',
                                                    'scenarios': [{'scenario': 'test',
                                                                   'expected_behavior_observed': True}],
                                                    'external_api_calls': 0,
                                                    'paid_continuation_enabled': False,
                                                    'autonomous_model_validation': 'NOT_RUN'}}}
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

    def test_caught_socket_sendfile_attempt_still_fails_acceptance(self):
        original = socket.socket.sendfile

        def attempt():
            import io
            try:
                with socket.socket() as client:
                    client.sendfile(io.BytesIO(b"offline test"))
            except RuntimeError:
                pass
            return {'evaluation': 'PASS', 'checks': [
                {'name': 'sendfile_attempt', 'passed': True}],
                    'external_api_calls': 0, 'paid_continuation_enabled': False,
                    'autonomous_model_validation': 'NOT_RUN'}

        with patch('offline_evaluation.run_offline_evaluation', side_effect=attempt):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(result['blocked_network_attempts'], 1)
        self.assertIs(socket.socket.sendfile, original)

    def test_swallowed_socket_connect_still_fails_and_restores_guard(self):
        original = socket.socket.connect

        def attempt():
            try:
                with socket.socket() as client:
                    client.connect(('127.0.0.1', 9))
            except RuntimeError:
                pass
            return {'evaluation': 'PASS', 'external_api_calls': 0,
                    'paid_continuation_enabled': False}

        with patch('offline_evaluation.run_offline_evaluation', side_effect=attempt):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(result['blocked_network_attempts'], 1)
        self.assertIs(socket.socket.connect, original)

    def test_local_asyncio_socketpair_send_is_not_counted_as_network(self):
        def exercise_local_signal():
            left, right = socket.socketpair()
            try:
                left.send(b'ping')
                received = right.recv(4)
            finally:
                left.close()
                right.close()
            return {'evaluation': 'PASS' if received == b'ping' else 'FAIL',
                    'checks': [{'name': 'local_signal', 'passed': received == b'ping'}],
                    'external_api_calls': 0, 'paid_continuation_enabled': False,
                    'autonomous_model_validation': 'NOT_RUN'}

        with patch('offline_evaluation.run_offline_evaluation',
                   side_effect=exercise_local_signal):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'PASS')
        self.assertEqual(result['blocked_network_attempts'], 0)

    def test_internet_bind_or_listen_attempts_fail_offline_acceptance(self):
        for operation in ('bind', 'listen'):
            with self.subTest(operation=operation):
                original = getattr(socket.socket, operation)

                def attempt():
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                            if operation == 'bind':
                                server.bind(('127.0.0.1', 0))
                            else:
                                server.listen(1)
                    except RuntimeError:
                        pass
                    return {'evaluation': 'PASS', 'checks': [
                        {'name': 'blocked_server', 'passed': True}],
                            'external_api_calls': 0, 'paid_continuation_enabled': False,
                            'autonomous_model_validation': 'NOT_RUN'}

                with patch('offline_evaluation.run_offline_evaluation', side_effect=attempt):
                    result = run_acceptance()
                self.assertEqual(result['evaluation'], 'FAIL')
                self.assertEqual(result['blocked_network_attempts'], 1)
                self.assertIs(getattr(socket.socket, operation), original)

    def test_unix_domain_bind_and_listen_remain_available(self):
        import tempfile
        from pathlib import Path

        def local_server():
            with tempfile.TemporaryDirectory() as folder:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(str(Path(folder) / 'local.sock'))
                    server.listen(1)
            return {'evaluation': 'PASS', 'checks': [
                {'name': 'unix_server', 'passed': True}],
                    'external_api_calls': 0, 'paid_continuation_enabled': False,
                    'autonomous_model_validation': 'NOT_RUN'}

        with patch('offline_evaluation.run_offline_evaluation', side_effect=local_server):
            result = run_acceptance()
        self.assertEqual(result['evaluation'], 'PASS')
        self.assertEqual(result['blocked_network_attempts'], 0)

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

    def test_summary_does_not_echo_malformed_network_count(self):
        from offline_acceptance import acceptance_summary
        for bad in ('token=SECRET_MARKER', True, -1, None):
            with self.subTest(bad=bad):
                summary = acceptance_summary({
                    'evaluation': 'FAIL', 'blocked_network_attempts': bad})
                self.assertIn('Blocked network attempts: UNKNOWN', summary)
                self.assertNotIn('SECRET_MARKER', summary)

    def test_summary_sanitizes_untrusted_error_types_and_check_labels(self):
        from offline_acceptance import acceptance_summary
        secret = 'token=SECRET_MARKER'
        report = {'evaluation': 'FAIL', 'blocked_network_attempts': 0,
                  'error_type': secret,
                  'suites': {'workflow': {'evaluation': 'FAIL',
                                         'error_type': secret,
                                         'checks': [{'name': secret, 'passed': False}]}}}
        summary = acceptance_summary(report)
        self.assertNotIn(secret, summary)
        self.assertIn('Error type: unnamed', summary)
        self.assertIn('Failed: unnamed', summary)

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

    def test_cli_default_rejects_unverified_json_pass(self):
        import contextlib
        import io
        import json
        from offline_acceptance import main
        result = {'evaluation': 'PASS', 'blocked_network_attempts': 0}
        with patch('offline_acceptance.run_acceptance', return_value=result), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main([]), 1)
        self.assertEqual(json.loads(output.getvalue())['evaluation'], 'FAIL')
        self.assertEqual(result['evaluation'], 'PASS')  # No mutation of source evidence.

    def test_cli_rejects_unsubstantiated_pass_in_both_output_modes(self):
        import contextlib
        import io
        import json
        from offline_acceptance import main

        contradictory = {'evaluation': 'PASS', 'blocked_network_attempts': 0,
                         'paid_continuation_enabled': False,
                         'autonomous_model_validation': 'NOT_RUN',
                         'suites': {}}
        for args in ([], ['--summary']):
            with self.subTest(args=args), patch('offline_acceptance.run_acceptance',
                    return_value=contradictory), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(args), 1)
            if args:
                self.assertIn('Offline acceptance: FAIL', output.getvalue())
            else:
                self.assertEqual(json.loads(output.getvalue())['evaluation'], 'FAIL')

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

    def test_duplicate_or_missing_check_names_cannot_claim_success(self):
        from offline_acceptance import _validated_suite
        base = {'evaluation': 'PASS', 'external_api_calls': 0,
                'paid_continuation_enabled': False,
                'autonomous_model_validation': 'NOT_RUN'}
        for labels in (['same', 'same'], ['same', ' same '], ['valid', ''], ['valid', '   '], ['valid', None]):
            with self.subTest(labels=labels):
                report = dict(base, checks=[{'name': label, 'passed': True}
                                            for label in labels])
                with self.assertRaisesRegex(ValueError, 'DUPLICATE_OR_MISSING_CHECK_LABEL'):
                    _validated_suite(report, 'checks', 'passed')

    def test_distinct_private_labels_cannot_collapse_to_same_public_check(self):
        from offline_acceptance import _validated_suite
        data = {'evaluation': 'PASS', 'checks': [
                    {'name': 'SECRET:one', 'passed': True},
                    {'name': 'SECRET:two', 'passed': True}],
                'external_api_calls': 0, 'paid_continuation_enabled': False,
                'autonomous_model_validation': 'NOT_RUN'}
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_SANITIZED_CHECK_LABEL'):
            _validated_suite(data, 'checks', 'passed')

    def test_distinct_private_scenarios_cannot_collapse_to_same_public_label(self):
        from offline_acceptance import _validated_suite
        data = {'evaluation': 'PASS', 'scenarios': [
                    {'scenario': 'private:one', 'expected_behavior_observed': True},
                    {'scenario': 'private:two', 'expected_behavior_observed': True}],
                'external_api_calls': 0, 'paid_continuation_enabled': False,
                'autonomous_model_validation': 'NOT_RUN'}
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_SANITIZED_CHECK_LABEL'):
            _validated_suite(data, 'scenarios', 'expected_behavior_observed')

    def test_displayed_check_labels_are_unique_after_trimming(self):
        from offline_acceptance import _validated_suite
        data = {'evaluation': 'PASS', 'checks': [
                    {'name': 'unnamed', 'passed': True},
                    {'name': 'SECRET:original', 'passed': True}],
                'external_api_calls': 0, 'paid_continuation_enabled': False,
                'autonomous_model_validation': 'NOT_RUN'}
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_SANITIZED_CHECK_LABEL'):
            _validated_suite(data, 'checks', 'passed')

    def test_duplicate_practice_scenarios_are_rejected(self):
        from offline_acceptance import _validated_suite
        result = {'evaluation': 'PASS',
                  'scenarios': [
                      {'scenario': 'repeated_case', 'expected_behavior_observed': True},
                      {'scenario': 'repeated_case', 'expected_behavior_observed': True}],
                  'external_api_calls': 0, 'paid_continuation_enabled': False,
                  'autonomous_model_validation': 'NOT_RUN'}
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_OR_MISSING_CHECK_LABEL'):
            _validated_suite(result, 'scenarios', 'expected_behavior_observed')

    def test_contradictory_pass_or_missing_safety_metadata_fails(self):
        from offline_acceptance import _validated_suite
        good = {'evaluation': 'PASS', 'checks': [{'name': 'fixture', 'passed': True}],
                'external_api_calls': 0, 'paid_continuation_enabled': False,
                'autonomous_model_validation': 'NOT_RUN'}
        for changed in ({'checks': [{'name': 'fixture', 'passed': False}]}, {'external_api_calls': False},
                        {'paid_continuation_enabled': True},
                        {'autonomous_model_validation': None}):
            with self.subTest(changed=changed):
                result = _validated_suite(dict(good, **changed), 'checks', 'passed')
                self.assertEqual(result['evaluation'], 'FAIL')
        self.assertEqual(_validated_suite(good, 'checks', 'passed')['evaluation'], 'PASS')
