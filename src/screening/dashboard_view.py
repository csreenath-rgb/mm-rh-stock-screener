"""Prepare scan-signal rows for the dashboard table.

Pure helpers (no Streamlit) so the table logic is unit-testable:
  * pct_upside        - computed % gain from current price to target price
  * signals_dataframe - build the display DataFrame (adds % Upside, drops the
                        volume_ratio noise column, orders + relabels columns)
  * apply_sort        - sort the table by any displayed column, asc or desc
"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

# Columns hidden from the dashboard table (none — volume_ratio is kept).
_DROP = ()

# Preferred left-to-right order (raw keys). Anything else is appended after,
# preserving its original order.
_ORDER = [
    "ticker", "score", "phase", "current_price", "target_price", "pct_upside",
    "risk_reward_ratio", "stop_loss", "entry_quality", "breakout_price", "rs_slope",
    "volume_ratio",
]

# Friendly column headers shown in the UI.
_LABELS = {
    "ticker": "Ticker", "score": "Score", "phase": "Phase",
    "current_price": "Current Price", "target_price": "Target Price",
    "pct_upside": "% Upside", "risk_reward_ratio": "R:R",
    "stop_loss": "Stop Loss", "entry_quality": "Entry Quality",
    "breakout_price": "Breakout Price", "rs_slope": "RS Slope",
    "volume_ratio": "Volume Ratio",
}


def _num(v) -> Optional[float]:
    """Return v as a number, or None if it is not a real number."""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def pct_upside(current_price, target_price) -> Optional[float]:
    """Percentage upside from current price to target: (target-current)*100/current.

    Returns None when either input is missing/non-numeric or the current price is
    zero, so the dashboard shows a blank cell rather than crashing or dividing by
    zero. Rounded to 2 decimal places.
    """
    cur, tgt = _num(current_price), _num(target_price)
    if cur in (None, 0) or tgt is None:
        return None
    return round((tgt - cur) * 100.0 / cur, 2)


def signals_dataframe(signals: List[Dict]) -> pd.DataFrame:
    """Build the dashboard DataFrame for a list of signal rows.

    Adds a computed '% Upside' column, removes the volume_ratio column, orders
    the columns sensibly, and relabels them for display. Returns an empty
    DataFrame for an empty/None input.
    """
    rows = list(signals or [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Computed upside from the raw price columns (before relabelling).
    df["pct_upside"] = [pct_upside(r.get("current_price"), r.get("target_price")) for r in rows]
    # Drop noise columns.
    df = df.drop(columns=[c for c in _DROP if c in df.columns])
    # Order: preferred columns that are present, then any extras (original order).
    known = [c for c in _ORDER if c in df.columns]
    extras = [c for c in df.columns if c not in known]
    df = df[known + extras]
    # Friendly headers.
    return df.rename(columns={k: v for k, v in _LABELS.items() if k in df.columns})


def apply_sort(df: pd.DataFrame, column: Optional[str], ascending: bool = False) -> pd.DataFrame:
    """Sort df by a displayed column. Empty df or unknown column -> unchanged.

    Missing values are pushed to the bottom regardless of direction so a blank
    cell never floats to the top.
    """
    if df is None or getattr(df, "empty", True) or not column or column not in df.columns:
        return df
    return df.sort_values(by=column, ascending=ascending, na_position="last").reset_index(drop=True)
