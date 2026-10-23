"""Rebind a trusted in-memory SDK snapshot to rebuilt application tools.

Never accept uploaded or client-supplied snapshots here. Nothing is persisted.
The original state must be consumed by the caller before copying it.
"""
import asyncio
from agents import RunState
from scripted_offline_model import ScriptedOfflineModel
from financial_approval_preview import pending_financial_request


def _check_request(state, expected):
    if expected is None:
        return
    try:
        _, _, actual = pending_financial_request(state)
    except ValueError as error:
        raise ValueError("SDK_APPROVED_REQUEST_CHANGED") from error
    if actual != expected:
        raise ValueError("SDK_APPROVED_REQUEST_CHANGED")


def rebind_offline_state(state, agent, *, expected_request_sha256=None):
    if type(agent.model) is not ScriptedOfflineModel:
        raise ValueError("LIVE_RESUME_DISABLED")
    if not isinstance(state, RunState):
        raise ValueError("SDK_RUN_STATE_INVALID")
    _check_request(state, expected_request_sha256)
    snapshot = state.to_json()
    restored = asyncio.run(RunState.from_json(agent, snapshot))
    # Check the detached snapshot too: the original can change during serialization.
    _check_request(restored, expected_request_sha256)
    return restored
