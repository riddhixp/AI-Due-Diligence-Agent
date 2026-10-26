"""Prepare an estimate for human review; never authorize or execute an API call.

USD estimates do not convert, replenish or reset the user's original GBP deposit.
These planned token/request ceilings are not yet a live spending-control system.
"""
import argparse
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
from pathlib import Path

from investigation_checkpoint import document_fingerprint
from synthetic_conflict_document import read_synthetic_conflict_pages

PRICING_URL = 'https://developers.openai.com/api/docs/models/gpt-5-mini'
PRICING_CHECKED = '2026-10-23'
MODEL = 'gpt-5-mini'
INPUT_USD_PER_MILLION = Decimal('0.25')
OUTPUT_USD_PER_MILLION = Decimal('2.00')


def _money(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('CREDIT_MUST_BE_DECIMAL_USD')
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError('CREDIT_MUST_BE_DECIMAL_USD') from error
    if not amount.is_finite() or amount < 0:
        raise ValueError('INVALID_REMAINING_CREDIT')
    return amount


def prepare_paid_test_plan(pdf_bytes, *, remaining_credit_usd=None,
                           max_requests=8, max_input_tokens_per_request=16000,
                           max_output_tokens_per_request=2048):
    """Return a blocked proposal, even when there is enough reported credit.

    Token ceilings cover the entire test, including continuations, not an
    allowance that resets on every approval. No credentials are read.
    """
    pages = read_synthetic_conflict_pages(pdf_bytes)
    limits = (max_requests, max_input_tokens_per_request, max_output_tokens_per_request)
    bounds = (8, 16000, 2048)
    for value, ceiling in zip(limits, bounds):
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError('INVALID_PLANNED_TOKEN_OR_REQUEST_LIMIT')
    per_request = (Decimal(max_input_tokens_per_request) * INPUT_USD_PER_MILLION
                   + Decimal(max_output_tokens_per_request) * OUTPUT_USD_PER_MILLION) / 1000000
    estimated_ceiling = per_request * max_requests
    # Double the estimate for planning headroom; do not claim a billing guarantee.
    proposed_reserve = (estimated_ceiling * 2).quantize(Decimal('0.01'), rounding=ROUND_CEILING)
    remaining = None if remaining_credit_usd is None else _money(remaining_credit_usd)
    blockers = ['EXPLICIT_PERMISSION_FOR_THIS_TEST_REQUIRED',
                'PAID_CONTINUATION_DISABLED', 'LIVE_SPEND_ENFORCEMENT_NOT_VALIDATED',
                'MODEL_AVAILABILITY_NOT_VERIFIED', 'PRICING_REVALIDATION_REQUIRED']
    if remaining is None:
        blockers.insert(0, 'REMAINING_CREDIT_UNKNOWN')
    elif remaining < proposed_reserve:
        blockers.insert(0, 'INSUFFICIENT_REPORTED_REMAINING_CREDIT')
    return {
        'status': 'PLANNING_ONLY', 'can_execute': False, 'api_calls': 0,
        'model': MODEL, 'model_availability_verified': False,
        'model_status_at_pricing_check': 'DEPRECATED_IN_DOCUMENTATION',
        'document_sha256': document_fingerprint(pdf_bytes), 'pdf_pages': len(pages),
        'test': 'synthetic_conflict_approval_and_correction',
        'funding': {'original_total_gbp': '5.00', 'includes_prior_usage': True,
                    'new_funding_authorized': False, 'automatic_top_up_authorized': False,
                    'remaining_credit_usd_reported': None if remaining is None else str(remaining),
                    'balance_verified_by_app': False, 'currency_conversion_performed': False},
        'planned_limits': {'max_model_requests_total': max_requests,
                           'max_input_tokens_per_request': max_input_tokens_per_request,
                           'max_output_tokens_per_request': max_output_tokens_per_request,
                           'reset_on_approval': False},
        'cost_estimate_usd': str(estimated_ceiling),
        'proposed_reserve_usd': str(proposed_reserve),
        'estimate_is_enforced_spending_cap': False,
        'estimate_requires_current_pricing': True,
        'pricing': {'source': PRICING_URL, 'checked_on': PRICING_CHECKED,
                    'input_per_million_usd': str(INPUT_USD_PER_MILLION),
                    'output_per_million_usd': str(OUTPUT_USD_PER_MILLION),
                    'cached_input_discount_assumed': False},
        'blockers': blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Prepare a paid test proposal without API calls.')
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--remaining-credit-usd', default=None)
    args = parser.parse_args(argv)
    try:
        plan = prepare_paid_test_plan(args.pdf.read_bytes(), remaining_credit_usd=args.remaining_credit_usd)
    except (ValueError, OSError) as error:
        parser.exit(2, f'Cannot prepare plan: {error}\n')
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
