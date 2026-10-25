"""Process-local request admission; no provider calls, pricing or permission grant."""
from threading import Lock


class ModelRequestBudget:
    """Atomically consume a whole-workflow quota before dispatch.

    Reservations are never refunded: a failed/cancelled request may have reached
    a provider. Reuse the same object across pauses; creating a new object resets
    the quota. This is not a token limit or a billing cap, and is not durable.
    """
    def __init__(self, maximum):
        if type(maximum) is not int or not 1 <= maximum <= 20:
            raise ValueError('INVALID_MODEL_REQUEST_BUDGET')
        self._maximum = maximum
        self._used = 0
        self._lock = Lock()

    def reserve(self):
        with self._lock:
            if self._used >= self._maximum:
                raise ValueError('MODEL_REQUEST_BUDGET_EXHAUSTED')
            self._used += 1
            return self._used

    def snapshot(self):
        with self._lock:
            return {'maximum': self._maximum, 'reserved': self._used,
                    'remaining': self._maximum - self._used}
