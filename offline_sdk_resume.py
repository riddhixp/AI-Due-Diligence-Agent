"""Execute a resumed SDK state only through an explicit injected offline runner.

The production pathway is deliberately disabled. A fake runner can test
argument forwarding and financial closure identity with zero API calls.
"""


def dry_run_resume(handoff, agent, runner, *, allow_live=False):
    if allow_live:
        raise ValueError("LIVE_RESUME_NOT_VERIFIED")
    if not isinstance(handoff, dict) or handoff.get("ready_for_live_run") is not False:
        raise ValueError("INVALID_HANDOFF")
    if handoff.get("reason") != "SDK_AGENT_TOOL_CLOSURES_NOT_REBOUND":
        raise ValueError("UNEXPECTED_HANDOFF_STATUS")
    state = handoff.get("sdk_state")
    financial = handoff.get("financial_state")
    if state is None or not isinstance(financial, dict):
        raise ValueError("MISSING_RESUME_STATE")
    if not getattr(runner, "offline_test_double", False):
        raise ValueError("OFFLINE_RUNNER_REQUIRED")
    execute = getattr(runner, "run", None)
    if not callable(execute):
        raise ValueError("INVALID_OFFLINE_RUNNER")
    result = execute(agent, state)
    return {
        "result": result,
        "model_resumed": False,
        "offline_simulation": True,
        "submissions_preserved": financial["submission_attempts"]["count"],
        "reviews_preserved": financial["review_state"]["reviewed_count"],
    }
