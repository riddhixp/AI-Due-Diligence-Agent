"""Allow SDK resumed execution only with a trusted, zero-network scripted model.

The live full-agent resume path remains disabled. This gate is used by the
real due-diligence entry point before any Runner call or credential lookup.
"""


def checked_resume_mode(checkpoint, pdf_bytes, sdk_state, model):
    if checkpoint is None:
        if sdk_state is not None or model is not None:
            raise ValueError("RESUME_CHECKPOINT_REQUIRED")
        return "FRESH_RUN"
    if pdf_bytes is None:
        raise ValueError("RESUME_REQUIRES_ORIGINAL_PDF")
    if sdk_state is None:
        raise ValueError("SDK_RUN_STATE_REQUIRED")
    from scripted_offline_model import ScriptedOfflineModel
    if type(model) is not ScriptedOfflineModel:
        raise ValueError("LIVE_RESUME_DISABLED")
    if not callable(getattr(model, "get_response", None)):
        raise ValueError("OFFLINE_MODEL_INVALID")
    if not callable(getattr(sdk_state, "get_interruptions", None)):
        raise ValueError("SDK_RUN_STATE_INVALID")
    return "OFFLINE_SDK_RESUME"
