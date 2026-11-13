"""Process-local one-shot SDK RunState dispatch guard.

RunState is unhashable. Identity tracking via weak references avoids retaining
sensitive transcript contents indefinitely. A dispatched state cannot be
retried in this process, including after an exception from the Runner.
This is not a cross-process idempotency guarantee.
"""
import threading
import weakref

_lock = threading.Lock()
_consumed = {}


def _forget_state(key, reference):
    with _lock:
        if _consumed.get(key) is reference:
            _consumed.pop(key, None)


def consume_sdk_resume_state(state):
    if state is None:
        raise ValueError("SDK_RUN_STATE_REQUIRED")
    key = id(state)
    with _lock:
        existing = _consumed.get(key)
        if existing is not None and existing() is state:
            raise ValueError("SDK_RUN_STATE_ALREADY_CONSUMED")
        try:
            reference = weakref.ref(
                state, lambda ref, key=key: _forget_state(key, ref),
            )
        except TypeError as exc:
            raise ValueError("SDK_RUN_STATE_NOT_WEAKREFABLE") from exc
        _consumed[key] = reference
