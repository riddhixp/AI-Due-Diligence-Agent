"""Finite numeric operations shared by financial checks and diagnostics."""
import math


def finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def finite_difference(left, right, *, digits=None):
    if not finite_number(left) or not finite_number(right):
        return None
    result = left - right
    if not finite_number(result):
        return None
    return round(result, digits) if digits is not None else result


def finite_percentage(numerator, denominator):
    if not finite_number(numerator) or not finite_number(denominator) or denominator <= 0:
        return None
    result = numerator / denominator * 100
    return round(result, 2) if finite_number(result) else None


def format_percentage(value):
    return f'{value:.2f}%' if finite_number(value) else 'Unavailable'
