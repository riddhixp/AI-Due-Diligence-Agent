"""Conservative bounds for optional live-model diligence tests."""


def permitted_turn_limit(requested=None, default=20, maximum=20):
    """Validate an agent-run turn cap without silently removing safeguards."""
    if requested is None:
        return default
    if isinstance(requested, bool) or not isinstance(requested, int):
        raise ValueError("Turn limit must be an integer.")
    if not 1 <= requested <= maximum:
        raise ValueError(f"Turn limit must be between 1 and {maximum}.")
    return requested
