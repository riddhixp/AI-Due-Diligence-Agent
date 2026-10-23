"""Decide which AI analyses may replace cached full diligence reports."""


def should_cache_report(smoke_test_mode):
    """Smoke tests are deliberately not persisted over completed analyses."""
    if not isinstance(smoke_test_mode, bool):
        raise TypeError("smoke_test_mode must be a boolean")
    return not smoke_test_mode
