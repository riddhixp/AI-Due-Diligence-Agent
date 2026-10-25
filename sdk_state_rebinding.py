"""Rebind a trusted in-memory SDK snapshot to rebuilt application tools.

Never accept uploaded or client-supplied snapshots here. Nothing is persisted.
The original state must be consumed by the caller before copying it.
"""
import asyncio
import warnings
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
    # Match SDK run_sync ownership: keep its thread-default loop available
    # across pauses. asyncio.run() would clear that reference without closing
    # the SDK-owned loop. Never drive a loop inside an active async context.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("SDK_STATE_REBIND_REQUIRES_SYNC_CONTEXT")
    policy = asyncio.get_event_loop_policy()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        try:
            loop = policy.get_event_loop()
        except RuntimeError:
            loop = policy.new_event_loop()
            policy.set_event_loop(loop)
    if loop.is_closed():
        loop = policy.new_event_loop()
        policy.set_event_loop(loop)
    snapshot = state.to_json()
    restored = loop.run_until_complete(RunState.from_json(agent, snapshot))
    # Check the detached snapshot too: the original can change during serialization.
    _check_request(restored, expected_request_sha256)
    return restored
