"""Preview one pending financial request without exposing SDK internals."""
import hashlib
import json
import math


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_FINANCIAL_ARGUMENT')
        result[key] = value
    return result


def inspect_financial_request(request):
    raw = getattr(request, 'raw_item', None)
    if (getattr(raw, 'type', None) != 'function_call'
            or getattr(raw, 'name', None) != 'submit_financial_data'):
        raise ValueError('UNEXPECTED_FINANCIAL_APPROVAL_TOOL')
    call_id = getattr(raw, 'call_id', None)
    arguments = getattr(raw, 'arguments', None)
    if not isinstance(call_id, str) or not call_id:
        raise ValueError('MISSING_FINANCIAL_CALL_ID')
    if not isinstance(arguments, str) or len(arguments) > 65536:
        raise ValueError('INVALID_FINANCIAL_ARGUMENTS')
    try:
        values = json.loads(arguments, object_pairs_hook=_unique_object)
        canonical = json.dumps(values, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError('INVALID_FINANCIAL_ARGUMENTS') from error
    if not isinstance(values, dict) or values.get('revenue_current') is None:
        raise ValueError('MISSING_PROPOSED_REVENUE')
    for key, value in values.items():
        if value is None:
            continue
        if key in ('company', 'currency', 'units'):
            if not isinstance(value, str) or len(value) > 256:
                raise ValueError('INVALID_FINANCIAL_METADATA')
        elif (type(value) not in (int, float) or abs(value) > 1e308
              or not math.isfinite(value)):
            raise ValueError('INVALID_FINANCIAL_VALUE')
    fingerprint = hashlib.sha256(json.dumps(
        [call_id, raw.name, canonical], separators=(',', ':')).encode()).hexdigest()
    return values, fingerprint


def pending_financial_request(state):
    inspect = getattr(state, 'get_interruptions', None)
    if not callable(inspect):
        raise ValueError('SDK_INTERRUPTION_UNAVAILABLE')
    requests = inspect()
    if not isinstance(requests, list) or len(requests) != 1:
        raise ValueError('SINGLE_FINANCIAL_APPROVAL_REQUIRED')
    values, fingerprint = inspect_financial_request(requests[0])
    return requests[0], values, fingerprint


def financial_approval_preview(handoff):
    if handoff.get('status') != 'AWAITING_APPROVAL':
        raise ValueError('NO_PENDING_FINANCIAL_APPROVAL')
    _, values, fingerprint = pending_financial_request(handoff['sdk_state'])
    previous = handoff['checkpoint']['financial_data']
    rows = []
    for key, value in values.items():
        if key in ('company', 'currency', 'units', 'fiscal_year', 'source_page') or key.endswith('_page'):
            continue
        old = previous.get(key)
        if key.startswith('reported_'):
            old = previous.get('reported', {}).get(key.removeprefix('reported_'))
        rows.append({'Metric': key.replace('_', ' ').capitalize(),
                     'Previous': old, 'Proposed': value,
                     'PDF page': values.get(key + '_page', values.get('source_page'))})
    return {'request_sha256': fingerprint,
            'metadata': {key: values.get(key) for key in ('company', 'fiscal_year', 'currency', 'units')},
            'metrics': rows}
