"""Prevent replaying the same SDK RunState in a scripted continuation.

SDK approval state is mutable; running the same state twice could execute tools
twice. Consume the particular state instance before attempting Runner.run_sync.
"""
import weakref

_consumed = weakref.WeakSet()


def consume_sdk_resume_state(state):
    if state is None:
        raise ValueError("SDK_RUN_STATE_REQUIRED")
    if state in _consumed:
        raise ValueError("SDK_RUN_STATE_ALREADY_CONSUMED")
    _consumed.add(state)
