"""Keep fresh analysis separate from an existing paused investigation."""


def fresh_analysis_block_reason(paused_investigation):
    if paused_investigation is not None:
        return ('Discard the paused investigation before starting a new analysis. '
                'Recording an approval or rejection does not resume it.')
    return None
