import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from due_diligence_engine import extract_pages
from proposed_financial_review import review_proposed_financial_request
from scripts.create_conflict_test_fixture import create_conflict_fixture
from synthetic_financial_fixture import conflict_submission_arguments


class ProposedFinancialReviewTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as folder:
            self.pages = extract_pages(create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes())
        blocker = patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def review(self, values):
        arguments = json.dumps(values)
        raw = SimpleNamespace(type='function_call', name='submit_financial_data',
                              call_id='proposal', arguments=arguments)
        state = SimpleNamespace(get_interruptions=lambda: [SimpleNamespace(raw_item=raw)])
        result = review_proposed_financial_request(state, self.pages)
        self.assertEqual(raw.arguments, arguments)
        return result

    def test_supported_proposal_passes_without_mutating_arguments(self):
        values = conflict_submission_arguments()
        original = copy.deepcopy(values)
        result = self.review(values)
        self.assertEqual(result['status'], 'PRELIMINARY_CHECKS_PASSED')
        self.assertEqual(values, original)
        self.assertEqual(len(result['request_sha256']), 64)

    def test_incorrect_revenue_fails_statement_review(self):
        result = self.review(conflict_submission_arguments(revenue_current=130))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(any(row['status'] != 'ROW_YEAR_MATCH' for row in result['statement_checks']))

    def test_unsupported_optional_figure_is_flagged(self):
        result = self.review(conflict_submission_arguments(operating_cash_flow=999, operating_cash_flow_page=2))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_missing_optional_citation_is_not_a_pass(self):
        result = self.review(conflict_submission_arguments(operating_cash_flow=50))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(result['optional_issues'])

    def test_incomplete_proposal_is_unavailable(self):
        result = self.review({'revenue_current': 120})
        self.assertEqual(result['status'], 'REVIEW_UNAVAILABLE')
        self.assertEqual(result['reason'], 'INCOMPLETE_PROPOSED_FINANCIALS')

    def test_out_of_document_primary_page_is_flagged(self):
        result = self.review(conflict_submission_arguments(source_page=3))
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(result['citation_issues'])
