"""Rebind a trusted in-memory SDK snapshot to rebuilt application tools.

Never accept uploaded or client-supplied snapshots here. Nothing is persisted.
The original state must be consumed by the caller before copying it.
"""
import asyncio
from agents import RunState
from scripted_offline_model import ScriptedOfflineModel


def rebind_offline_state(state, agent):
    if type(agent.model) is not ScriptedOfflineModel:
        raise ValueError("LIVE_RESUME_DISABLED")
    if not isinstance(state, RunState):
        raise ValueError("SDK_RUN_STATE_INVALID")
    snapshot = state.to_json()
    return asyncio.run(RunState.from_json(agent, snapshot))
