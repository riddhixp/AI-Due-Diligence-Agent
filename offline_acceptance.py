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
    if any(type(label) is not str or not label for label in labels) or len(set(labels)) != len(labels):
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
    if len(set(output_labels)) != len(output_labels):
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


def acceptance_summary(report):
    """Keep the full JSON available while offering a readable local checklist."""
    if not isinstance(report, dict):
        report = {}
    lines = [f"Offline acceptance: {report.get('evaluation', 'FAIL')}"]
    suites = report.get('suites', {})
    if not isinstance(suites, dict):
        suites = {}
        lines.append('Suites: FAIL (invalid suite collection)')
    for name, suite in suites.items():
        if not isinstance(suite, dict):
            lines.append(f"{name}: FAIL (invalid suite result)")
            continue
        rows = suite.get('checks', suite.get('scenarios', []))
        if not isinstance(rows, list):
            rows = []
        passed = sum(isinstance(row, dict) and
                     row.get('passed', row.get('expected_behavior_observed')) is True
                     for row in rows)
        lines.append(f"{name}: {suite.get('evaluation', 'FAIL')} ({passed}/{len(rows)} checks)")
        if suite.get('error_type'):
            lines.append(f"  Error type: {suite['error_type']}")
        for row in rows:
            if not isinstance(row, dict):
                lines.append("  Failed: invalid check result")
            elif row.get('passed', row.get('expected_behavior_observed')) is not True:
                lines.append(f"  Failed: {row.get('name', row.get('scenario', 'unnamed'))}")
    if report.get('error_type'):
        lines.append(f"Error type: {report['error_type']}")
    lines.append(f"Blocked network attempts: {report.get('blocked_network_attempts', 'UNKNOWN')}")
    lines.append('Scripted checks only; autonomous model validation NOT_RUN; paid continuation disabled.')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', action='store_true', help='Print a short checklist instead of JSON')
    args = parser.parse_args(argv)
    report = run_acceptance()
    print(acceptance_summary(report) if args.summary else json.dumps(report, indent=2))
    return 0 if report['evaluation'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
