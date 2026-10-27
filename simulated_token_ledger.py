"""Offline-only, process-local ledger for simulated token usage.

Optionally wired to a scripted offline model only. Does not meter provider
usage, unreported tokens or enforce billing.
"""
from threading import Lock


class SimulatedTokenLedger:
    """Record complete, explicitly simulated request usage without resets."""

    def __init__(self, maximum_input, maximum_output):
        for value in (maximum_input, maximum_output):
            if type(value) is not int or not 1 <= value <= 128000:
                raise ValueError("INVALID_SIMULATED_TOKEN_LIMIT")
        self._limits = (maximum_input, maximum_output)
        self._totals = [0, 0]
        self._requests = 0
        self._lock = Lock()

    def __setattr__(self, name, value):
        if name in ("_limits", "_totals", "_requests", "_lock") and name in self.__dict__:
            raise ValueError("SIMULATED_TOKEN_LEDGER_STATE_IMMUTABLE")
        super().__setattr__(name, value)

    def __copy__(self):
        raise ValueError("SIMULATED_TOKEN_LEDGER_CANNOT_BE_COPIED")

    def __deepcopy__(self, memo):
        raise ValueError("SIMULATED_TOKEN_LEDGER_CANNOT_BE_COPIED")

    def __reduce_ex__(self, protocol):
        raise ValueError("SIMULATED_TOKEN_LEDGER_CANNOT_BE_SERIALIZED")

    def record(self, input_tokens, output_tokens):
        """Fail closed before accounting a request that exceeds either cap."""
        if any(type(v) is not int or v < 0 for v in (input_tokens, output_tokens)):
            raise ValueError("INVALID_SIMULATED_TOKEN_USAGE")
        with self._lock:
            new_input = self._totals[0] + input_tokens
            new_output = self._totals[1] + output_tokens
            if new_input > self._limits[0] or new_output > self._limits[1]:
                raise ValueError("SIMULATED_TOKEN_LIMIT_EXCEEDED")
            self._totals[:] = [new_input, new_output]
            object.__setattr__(self, "_requests", self._requests + 1)
            return self.snapshot_unlocked()

    def snapshot_unlocked(self):
        return {
            "simulated": True,
            "requests_recorded": self._requests,
            "input_tokens": self._totals[0],
            "output_tokens": self._totals[1],
            "input_remaining": self._limits[0] - self._totals[0],
            "output_remaining": self._limits[1] - self._totals[1],
            "provider_usage_verified": False,
            "billing_cap_enforced": False,
        }

    def snapshot(self):
        with self._lock:
            return self.snapshot_unlocked()
