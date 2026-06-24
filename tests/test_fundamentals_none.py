"""Regression tests: fundamentals analysis must not crash on None metric values,
and must flag when a stock's cached fundamentals are entirely unavailable.

Cached fundamentals JSON can contain keys present with value None (the metric
could not be computed). Previously this raised
'TypeError: > not supported between NoneType and int' and silently dropped the
stock from the scan. analyze_fundamentals_for_signal must treat None as neutral
and report fundamentals_available=False so unavailable stocks are visible.
"""

from src.data.fundamentals_fetcher import analyze_fundamentals_for_signal


def test_all_none_fields_do_not_crash_and_flag_unavailable():
    qd = {
        "revenue_yoy_change": None,
        "revenue_qoq_change": None,
        "eps_yoy_change": None,
        "inventory_qoq_change": None,
    }
    result = analyze_fundamentals_for_signal(qd)
    assert result["revenue_trend"] == "flat"
    assert result["eps_trend"] == "flat"
    assert result["inventory_signal"] == "neutral"
    assert result["sequential_revenue_declining"] is False
    assert result["fundamentals_available"] is False  # all metrics None


def test_partial_none_uses_present_values_and_flags_available():
    qd = {
        "revenue_yoy_change": 12.0,   # accelerating
        "revenue_qoq_change": None,
        "eps_yoy_change": None,        # -> 0 -> flat
        "inventory_qoq_change": 20.0,  # -> negative
    }
    result = analyze_fundamentals_for_signal(qd)
    assert result["revenue_trend"] == "accelerating"
    assert result["eps_trend"] == "flat"
    assert result["inventory_signal"] == "negative"
    assert result["fundamentals_available"] is True  # at least one real value


def test_numeric_values_still_work():
    qd = {
        "revenue_yoy_change": 15.0,
        "revenue_qoq_change": -10.0,   # sequential decline (< -2)
        "eps_yoy_change": 20.0,
        "inventory_qoq_change": 2.0,
    }
    result = analyze_fundamentals_for_signal(qd)
    assert result["revenue_trend"] == "accelerating"
    assert result["eps_trend"] == "accelerating"
    assert result["inventory_signal"] == "neutral"
    assert result["sequential_revenue_declining"] is True
    assert result["supports_breakout"] is False  # blocked by sequential decline
    assert result["fundamentals_available"] is True


def test_empty_dict_returns_unknown_and_unavailable():
    result = analyze_fundamentals_for_signal({})
    assert result["revenue_trend"] == "unknown"
    assert result["supports_breakout"] is False
    assert result["fundamentals_available"] is False


def test_missing_keys_default_to_neutral_and_unavailable():
    # Keys absent entirely (not even None) must be safe and flagged unavailable.
    result = analyze_fundamentals_for_signal({"some_other_field": 1})
    assert result["revenue_trend"] == "flat"
    assert result["eps_trend"] == "flat"
    assert result["fundamentals_available"] is False
