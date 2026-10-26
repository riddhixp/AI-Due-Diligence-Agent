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

    def __setattr__(self, name, value):
        if name == "_maximum" and "_maximum" in self.__dict__:
            raise ValueError("MODEL_REQUEST_BUDGET_LIMIT_IMMUTABLE")
        super().__setattr__(name, value)

    def __copy__(self):
        raise ValueError('MODEL_REQUEST_BUDGET_CANNOT_BE_COPIED')

    def __deepcopy__(self, memo):
        raise ValueError('MODEL_REQUEST_BUDGET_CANNOT_BE_COPIED')

    def __reduce_ex__(self, protocol):
        raise ValueError('MODEL_REQUEST_BUDGET_CANNOT_BE_SERIALIZED')

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
