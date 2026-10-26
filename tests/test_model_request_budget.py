import asyncio
import copy
import pickle
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from financial_approval_resume import decide_and_resume_offline
from model_request_budget import ModelRequestBudget
from offline_correction_workflow import start_offline_correction_workflow
from scripted_offline_model import ScriptedOfflineModel
from scripts.create_conflict_test_fixture import create_conflict_fixture


class ModelRequestBudgetTests(unittest.TestCase):
    def test_invalid_limits_fail(self):
        for value in [None, True, 0, -1, 21, 2.0, '2']:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'INVALID_MODEL_REQUEST_BUDGET'):
                ModelRequestBudget(value)

    def test_exact_quota_and_snapshot_are_independent(self):
        budget = ModelRequestBudget(2)
        self.assertEqual(budget.reserve(), 1)
        self.assertEqual(budget.reserve(), 2)
        snapshot = budget.snapshot()
        snapshot['reserved'] = 0
        with self.assertRaisesRegex(ValueError, 'MODEL_REQUEST_BUDGET_EXHAUSTED'):
            budget.reserve()
        self.assertEqual(budget.snapshot(), {'maximum': 2, 'reserved': 2, 'remaining': 0})

    def test_concurrent_requests_cannot_overbook(self):
        budget = ModelRequestBudget(3)
        def claim(_):
            try:
                budget.reserve()
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=32) as pool:
            self.assertEqual(sum(pool.map(claim, range(32))), 3)
        self.assertEqual(budget.snapshot()['remaining'], 0)

    def test_budget_ceiling_cannot_be_raised_after_creation(self):
        budget = ModelRequestBudget(1)
        with self.assertRaisesRegex(ValueError, 'MODEL_REQUEST_BUDGET_LIMIT_IMMUTABLE'):
            budget._maximum = 20
        self.assertEqual(budget.reserve(), 1)
        with self.assertRaisesRegex(ValueError, 'MODEL_REQUEST_BUDGET_EXHAUSTED'):
            budget.reserve()
        self.assertEqual(budget.snapshot(), {'maximum': 1, 'reserved': 1, 'remaining': 0})

    def test_copy_and_serialization_cannot_reset_or_fork_quota(self):
        budget = ModelRequestBudget(1)
        budget.reserve()
        for operation in (copy.copy, copy.deepcopy):
            with self.subTest(operation=operation.__name__), self.assertRaisesRegex(
                    ValueError, 'MODEL_REQUEST_BUDGET_CANNOT_BE_COPIED'):
                operation(budget)
        with self.assertRaisesRegex(ValueError, 'MODEL_REQUEST_BUDGET_CANNOT_BE_SERIALIZED'):
            pickle.dumps(budget)
        self.assertEqual(budget.snapshot()['remaining'], 0)

    def test_model_cannot_replace_or_disable_bound_request_budget(self):
        budget = ModelRequestBudget(1)
        model = ScriptedOfflineModel(request_budget=budget)
        for replacement in (None, ModelRequestBudget(20), budget):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(
                    ValueError, 'MODEL_REQUEST_BUDGET_IMMUTABLE'):
                model.request_budget = replacement
        self.assertIs(model.request_budget, budget)
        asyncio.run(model.get_response())
        with self.assertRaisesRegex(ValueError, 'MODEL_REQUEST_BUDGET_EXHAUSTED'):
            asyncio.run(model.get_response())
        self.assertEqual(model.calls, 1)

    def test_failed_dispatch_keeps_reservation(self):
        budget = ModelRequestBudget(1)
        model = ScriptedOfflineModel(request_budget=budget)
        model.responses = []
        with self.assertRaises(AssertionError):
            asyncio.run(model.get_response())
        with self.assertRaisesRegex(ValueError, 'MODEL_REQUEST_BUDGET_EXHAUSTED'):
            asyncio.run(model.get_response())
        self.assertEqual(model.calls, 1)
        self.assertEqual(budget.snapshot()['reserved'], 1)

    def test_invalid_budget_object_cannot_be_used_as_model(self):
        with self.assertRaisesRegex(ValueError, 'INVALID_MODEL_REQUEST_BUDGET'):
            ScriptedOfflineModel(request_budget=object())

    def test_whole_workflow_quota_survives_approval_pause(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        budget = ModelRequestBudget(5)
        model = ScriptedOfflineModel(request_budget=budget)
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch('offline_correction_workflow.ScriptedOfflineModel', return_value=model):
            fixture = start_offline_correction_workflow(pdf)
            self.assertEqual(budget.snapshot()['reserved'], 2)
            result = decide_and_resume_offline(fixture['handoff'], pdf, True, model)
            self.assertEqual(result['status'], 'AWAITING_APPROVAL')
            self.assertEqual(budget.snapshot()['reserved'], 5)
            correction = result['handoff']
            with self.assertRaisesRegex(ValueError, 'MODEL_REQUEST_BUDGET_EXHAUSTED'):
                decide_and_resume_offline(correction, pdf, True, model)
        self.assertEqual(model.calls, 5)
        self.assertEqual(budget.snapshot()['reserved'], 5)
        self.assertEqual(correction['status'], 'FAILED')
        # The approved pending tool runs before the next model call is blocked.
        # Preserve it as unreviewed progress, never a completed result.
        progress = correction['failure_checkpoint']
        self.assertEqual(progress['financial_data']['revenue_current'], 120)
        self.assertEqual(progress['reviewed_count'], 1)
        self.assertEqual(progress['submission_count'], 2)
        self.assertIsNone(progress['review_status'])

    def test_sufficient_shared_quota_completes_scripted_workflow(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        budget = ModelRequestBudget(7)
        model = ScriptedOfflineModel(request_budget=budget)
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch('offline_correction_workflow.ScriptedOfflineModel', return_value=model):
            fixture = start_offline_correction_workflow(pdf)
            result = decide_and_resume_offline(fixture['handoff'], pdf, True, model)
            result = decide_and_resume_offline(result['handoff'], pdf, True, model)
        self.assertEqual(result['status'], 'COMPLETED_OFFLINE')
        self.assertEqual(result['financial']['revenue_current'], 120)
        self.assertEqual(result['external_api_calls'], 0)
        self.assertTrue(result['evaluation']['simulation'])
        self.assertEqual(model.calls, 7)
        self.assertEqual(budget.snapshot()['remaining'], 0)
