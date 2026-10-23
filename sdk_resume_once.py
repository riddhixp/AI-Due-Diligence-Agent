"""One-shot SDK RunState dispatch guard for offline continuation.

RunState is unhashable. Track object identity via weak references rather than
using WeakSet, which requires hashable SDK state objects.
"""
import weakref

_consumed = {}


def consume_sdk_resume_state(state):
    if state is None:
        raise ValueError("SDK_RUN_STATE_REQUIRED")
    key = id(state)
    existing = _consumed.get(key)
    if existing is not None and existing() is state:
        raise ValueError("SDK_RUN_STATE_ALREADY_CONSUMED")
    try:
        reference = weakref.ref(state, lambda ref, key=key: _consumed.pop(key, None))
    except TypeError as exc:
        raise ValueError("SDK_RUN_STATE_NOT_WEAKREFABLE") from exc
    _consumed[key] = reference
