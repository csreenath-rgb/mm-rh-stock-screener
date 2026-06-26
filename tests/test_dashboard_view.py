"""TDD: dashboard table prep — computed % upside, dropped noise columns, sorting.

These are pure functions so the dashboard's table logic is unit-tested without
launching Streamlit.
"""
import math

import pandas as pd
import pytest

from src.screening.dashboard_view import pct_upside, signals_dataframe, apply_sort


def _sig(**kw):
    base = dict(ticker="AAA", score=80, phase="Phase 2 - Advancing",
                current_price=100.0, target_price=120.0, stop_loss=95.0,
                risk_reward_ratio=2.0, entry_quality="Good",
                breakout_price=101.0, rs_slope=0.5, volume_ratio=1.3)
    base.update(kw)
    return base


# ----------------------- pct_upside -----------------------

def test_pct_upside_basic():
    assert pct_upside(100, 120) == 20.0
    assert pct_upside(50, 75) == 50.0

def test_pct_upside_rounds_2dp():
    assert pct_upside(3, 4) == 33.33

def test_pct_upside_negative_when_target_below_current():
    assert pct_upside(100, 90) == -10.0

def test_pct_upside_guards_zero_and_missing():
    assert pct_upside(0, 120) is None      # no divide-by-zero
    assert pct_upside(None, 120) is None
    assert pct_upside(100, None) is None
    assert pct_upside("x", 120) is None


# ----------------------- signals_dataframe -----------------------

def test_adds_pct_upside_column_with_values():
    df = signals_dataframe([_sig(current_price=100.0, target_price=125.0)])
    assert "% Upside" in df.columns
    assert df["% Upside"].iloc[0] == 25.0

def test_keeps_volume_ratio():
    df = signals_dataframe([_sig()])
    assert "Volume Ratio" in df.columns
    assert df["Volume Ratio"].iloc[0] == 1.3

def test_column_order_upside_after_target_and_ticker_first():
    cols = list(signals_dataframe([_sig()]).columns)
    assert cols[0] == "Ticker"
    assert cols.index("% Upside") == cols.index("Target Price") + 1

def test_empty_signals_returns_empty_dataframe():
    df = signals_dataframe([])
    assert isinstance(df, pd.DataFrame) and df.empty


# ----------------------- apply_sort -----------------------

def test_apply_sort_descending_by_score():
    df = signals_dataframe([_sig(ticker="LOW", score=70), _sig(ticker="HIGH", score=95)])
    out = apply_sort(df, "Score", ascending=False)
    assert list(out["Ticker"]) == ["HIGH", "LOW"]

def test_apply_sort_ascending_by_upside():
    df = signals_dataframe([
        _sig(ticker="BIG", current_price=100.0, target_price=200.0),   # +100%
        _sig(ticker="SMALL", current_price=100.0, target_price=110.0), # +10%
    ])
    out = apply_sort(df, "% Upside", ascending=True)
    assert list(out["Ticker"]) == ["SMALL", "BIG"]

def test_apply_sort_missing_column_returns_unchanged():
    df = signals_dataframe([_sig(ticker="A"), _sig(ticker="B")])
    out = apply_sort(df, "Nonexistent", ascending=True)
    assert list(out["Ticker"]) == ["A", "B"]

def test_apply_sort_nulls_sink_to_bottom():
    df = signals_dataframe([
        _sig(ticker="HASUP", current_price=100.0, target_price=150.0),
        _sig(ticker="NOUP", current_price=100.0, target_price=None),   # upside None
    ])
    out = apply_sort(df, "% Upside", ascending=False)
    assert list(out["Ticker"]) == ["HASUP", "NOUP"]
