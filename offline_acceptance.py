"""Run scripted acceptance checks with outbound socket operations blocked."""
import argparse
import contextlib
import io
import json
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch


def _validated_suite(result, rows_key, status_key):
    """Reject empty or contradictory success evidence before summarising it."""
    if not isinstance(result, dict):
        raise ValueError('INVALID_SUITE_RESULT')
    rows = result.get(rows_key)
    if not isinstance(rows, list) or not rows:
        raise ValueError('MISSING_SUITE_CHECKS')
    if any(not isinstance(row, dict) or type(row.get(status_key)) is not bool for row in rows):
        raise ValueError('INVALID_SUITE_CHECKS')
    passed = (result.get('evaluation') == 'PASS'
              and all(row[status_key] for row in rows)
              and type(result.get('external_api_calls')) is int
              and result['external_api_calls'] == 0
              and result.get('paid_continuation_enabled') is False
              and result.get('autonomous_model_validation') == 'NOT_RUN')
    # A PASS cannot be credited to duplicate check labels that might disguise
    # omitted validation coverage. This is evidence hygiene, not model scoring.
    labels = [row.get('name' if rows_key == 'checks' else 'scenario') for row in rows]
    if any(type(label) is not str or not label.strip() for label in labels) or len(set(label.strip() for label in labels)) != len(labels):
        raise ValueError('DUPLICATE_OR_MISSING_CHECK_LABEL')

    # Row-level details also may contain PDF text, credentials or verbose errors.
    safe_rows = []
    for row in rows:
        label_key = 'name' if rows_key == 'checks' else 'scenario'
        label = row.get(label_key)
        # Only controlled, short plain-text labels can appear in public output.
        if type(label) is not str or len(label) > 100 or not label.isascii() or not all(
                char.isalnum() or char in ' _-.' for char in label):
            label = 'unnamed'
        safe_rows.append({label_key: label, status_key: row[status_key]})
    # Different unsafe labels may both be redacted to 'unnamed'. Do not
    # misrepresent them as distinguishable independent checks in a PASS report.
    output_labels = [row['name' if rows_key == 'checks' else 'scenario'] for row in safe_rows]
    if len(set(label.strip() for label in output_labels)) != len(output_labels):
        raise ValueError('DUPLICATE_SANITIZED_CHECK_LABEL')
    # Preserve only the fields needed by the local summary and machine checks.
    # Arbitrary suite metadata can include document text or secret-bearing errors.
    return {
        'evaluation': 'PASS' if passed else 'FAIL',
        rows_key: safe_rows,
        'external_api_calls': result.get('external_api_calls'),
        'paid_continuation_enabled': result.get('paid_continuation_enabled'),
        'autonomous_model_validation': result.get('autonomous_model_validation'),
    }


def run_acceptance():
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append(True)
        raise RuntimeError('OFFLINE_NETWORK_FORBIDDEN')

    # asyncio uses AF_UNIX socket pairs for its local wake-up notifications.
    # Blocking those internal writes can deadlock the event loop. Only allow
    # local-domain socket I/O; AF_INET / AF_INET6 traffic stays prohibited.
    def local_socket_send(original):
        def guarded(sock, *args, **kwargs):
            if sock.family == socket.AF_UNIX:
                return original(sock, *args, **kwargs)
            return blocked(sock, *args, **kwargs)
        return guarded

    # Keep the guard active during imports as well as execution. The attempt
    # count makes a swallowed network error a failed acceptance result too.
    report = {'evaluation': 'FAIL', 'execution_mode': 'SCRIPTED_OFFLINE_ACCEPTANCE',
              'autonomous_model_validation': 'NOT_RUN',
              'paid_continuation_enabled': False}
    try:
        with patch.object(socket.socket, 'connect', blocked), \
             patch.object(socket.socket, 'connect_ex', blocked), \
             patch.object(socket.socket, 'sendto', local_socket_send(socket.socket.sendto)), \
             patch.object(socket.socket, 'send', local_socket_send(socket.socket.send)), \
             patch.object(socket.socket, 'sendall', local_socket_send(socket.socket.sendall)), \
             patch.object(socket.socket, 'sendmsg', local_socket_send(getattr(socket.socket, 'sendmsg', blocked)), create=True), \
             patch.object(socket.socket, 'sendfile', blocked), \
             patch.object(socket.socket, 'bind', local_socket_send(socket.socket.bind)), \
             patch.object(socket.socket, 'listen', local_socket_send(socket.socket.listen)), \
             patch.object(socket, 'create_connection', blocked), \
             patch.object(socket, 'getaddrinfo', blocked), \
             contextlib.redirect_stdout(io.StringIO()):
            from offline_evaluation import run_offline_evaluation
            from practice_scenarios import run_practice_suite
            from scripts.create_conflict_test_fixture import create_conflict_fixture
            def capture(check, rows_key, status_key):
                try:
                    return _validated_suite(check(), rows_key, status_key)
                except Exception as error:
                    return {'evaluation': 'FAIL', 'error_type': type(error).__name__}

            workflow = capture(run_offline_evaluation, 'checks', 'passed')

            def practice():
                with tempfile.TemporaryDirectory() as folder:
                    pdf = create_conflict_fixture(Path(folder) / 'synthetic.pdf').read_bytes()
                return run_practice_suite(pdf)

            failures = capture(practice, 'scenarios', 'expected_behavior_observed')
            report['suites'] = {'workflow': workflow, 'failure_practice': failures}
            if all(result.get('evaluation') == 'PASS'
                   and result.get('external_api_calls') == 0
                   and result.get('paid_continuation_enabled') is False
                   for result in (workflow, failures)) and not attempts:
                report['evaluation'] = 'PASS'
    except Exception as error:
        # Do not print exception messages, PDF contents, or credentials.
        report['error_type'] = type(error).__name__
    report['blocked_network_attempts'] = len(attempts)
    return report



def _safe_summary_label(value):
    """Limit summary-only labels to short, non-sensitive identifiers."""
    if (type(value) is str and 0 < len(value) <= 100 and value.isascii()
            and all(c.isalnum() or c in ' _-.' for c in value)):
        return value
    return 'unnamed'


def acceptance_summary(report):
    """Keep the full JSON available while offering a readable local checklist."""
    if not isinstance(report, dict):
        report = {}
    # A summary must never advertise success based solely on an untrusted
    # top-level PASS claim when the suites or network evidence disagree.
    suites = report.get('suites')
    verified = (report.get('evaluation') == 'PASS'
                and type(report.get('blocked_network_attempts')) is int
                and report['blocked_network_attempts'] == 0
                and isinstance(suites, dict)
                and set(suites) == {'workflow', 'failure_practice'}
                and all(isinstance(suite, dict) and suite.get('evaluation') == 'PASS'
                        and suite.get('external_api_calls') == 0
                        and suite.get('paid_continuation_enabled') is False
                        and suite.get('autonomous_model_validation') == 'NOT_RUN'
                        and isinstance(suite.get('checks' if name == 'workflow' else 'scenarios'), list)
                        and bool(suite['checks' if name == 'workflow' else 'scenarios'])
                        and all(type(row.get('passed' if name == 'workflow' else 'expected_behavior_observed')) is bool
                                and row['passed' if name == 'workflow' else 'expected_behavior_observed']
                                for row in suite['checks' if name == 'workflow' else 'scenarios']
                                if isinstance(row, dict))
                        and all(isinstance(row, dict) for row in suite['checks' if name == 'workflow' else 'scenarios'])
                        for name, suite in suites.items()))
    lines = [f"Offline acceptance: {'PASS' if verified else 'FAIL'}"]
    suites = report.get('suites', {})
    if not isinstance(suites, dict):
        suites = {}
        lines.append('Suites: FAIL (invalid suite collection)')
    for name, suite in suites.items():
        if not isinstance(suite, dict):
            lines.append(f"{name}: FAIL (invalid suite result)")
            continue
        # Do not substitute another suite's rows when the expected collection
        # is missing. Such fallback can make a broken report look complete.
        expected_key = 'checks' if name == 'workflow' else 'scenarios'
        outcome_key = 'passed' if name == 'workflow' else 'expected_behavior_observed'
        rows = suite.get(expected_key, [])
        if not isinstance(rows, list):
            rows = []
        # Use only the result field belonging to this suite.
        passed = sum(isinstance(row, dict) and row.get(outcome_key) is True
                     for row in rows)
        # Never echo an arbitrary suite status or advertise a passing suite
        # when its check rows or safety metadata do not corroborate it.
        suite_ok = (name in ('workflow', 'failure_practice')
                    and suite.get('evaluation') == 'PASS'
                    and suite.get('external_api_calls') == 0
                    and suite.get('paid_continuation_enabled') is False
                    and suite.get('autonomous_model_validation') == 'NOT_RUN'
                    and isinstance(suite.get(expected_key), list)
                    and bool(suite[expected_key])
                    and all(isinstance(row, dict) and row.get(outcome_key) is True
                            for row in suite[expected_key])
                    and not suite.get('error_type'))
        lines.append(f"{_safe_summary_label(name)}: {'PASS' if suite_ok else 'FAIL'} ({passed}/{len(rows)} checks)")
        if suite.get('error_type'):
            lines.append(f"  Error type: {_safe_summary_label(suite['error_type'])}")
        for row in rows:
            if not isinstance(row, dict):
                lines.append("  Failed: invalid check result")
            elif row.get(outcome_key) is not True:
                lines.append(f"  Failed: {_safe_summary_label(row.get('name', row.get('scenario', 'unnamed')))}")
    if report.get('error_type'):
        lines.append(f"Error type: {_safe_summary_label(report['error_type'])}")
    count = report.get('blocked_network_attempts')
    safe_count = count if type(count) is int and count >= 0 else 'UNKNOWN'
    lines.append(f"Blocked network attempts: {safe_count}")
    lines.append('Scripted checks only; autonomous model validation NOT_RUN; paid continuation disabled.')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', action='store_true', help='Print a short checklist instead of JSON')
    args = parser.parse_args(argv)
    report = run_acceptance()
    summary = acceptance_summary(report)
    # Apply the same evidence gate to JSON, text, and the process exit code.
    # A contradictory top-level PASS must not pass a CI job.
    verified = summary.splitlines()[0] == 'Offline acceptance: PASS'
    if isinstance(report, dict) and not verified:
        report = dict(report, evaluation='FAIL')
    print(summary if args.summary else json.dumps(report, indent=2))
    return 0 if verified else 1


if __name__ == '__main__':
    raise SystemExit(main())
