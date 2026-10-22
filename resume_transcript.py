"""Safely inspect a captured agent run transcript before any future replay.

No API calls. Tool payloads may include sensitive document content, so only
keep transcripts in memory; never log or persist them automatically.
"""


def extract_resume_input(error):
    """Return the SDK's interrupted run input if exposed, else None.

    Some SDK versions expose input on MaxTurnsExceeded while others do not.
    Do not invent history or convert raw model internals into a new prompt.
    """
    run_data = getattr(error, "run_data", None)
    state = getattr(run_data, "input", None) if run_data is not None else None
    if not isinstance(state, list) or not state:
        return None
    return list(state)


def inspect_resume_input(state):
    """Explicitly distinguish retrievable transcript from proven resumability."""
    if not isinstance(state, list) or not state:
        return {"transcript_present": False, "can_resume": False,
                "reason": "NO_SDK_TRANSCRIPT"}
    return {"transcript_present": True, "can_resume": False,
            "reason": "REPLAY_NOT_VALIDATED", "items": len(state)}


def inspect_replay_boundary(state):
    """Check transcript shape without exposing its content or claiming replay."""
    from replay_boundary import validate_replay_boundary

    initial = inspect_resume_input(state)
    if not initial["transcript_present"]:
        return initial
    boundary = validate_replay_boundary(state)
    return {
        "transcript_present": True,
        "can_resume": False,
        "boundary_safe": boundary["safe_boundary"],
        "reason": boundary["reason"],
        "items": len(state),
    }
