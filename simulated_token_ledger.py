"""Offline-only, process-local ledger for simulated token usage.

Not wired to a provider. Does not meter unreported tokens or enforce billing.
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
            self._requests += 1
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
