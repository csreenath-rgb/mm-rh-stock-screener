"""Scan-size safety guard for the memory-limited dashboard (e.g. Streamlit Cloud free tier, ~1 GB RAM).

Pure, testable logic that classifies a requested scan as ok / warn / block based
on how much memory it is likely to need. The dashboard uses this to disable the
Run button (block) or show a caution (warn) before launching a scan.
"""

from typing import Optional, Tuple

# Approx upper bounds that are comfortable in ~1 GB RAM.
CUSTOM_BLOCK_OVER = 150   # more tickers than this -> block on limited hosting
CUSTOM_WARN_OVER = 50     # more than this -> warn

# Per-index classification (the full universe is far too large for 1 GB).
_INDEX_LEVELS = {
    "all": ("block", "The full ~3,800-stock universe needs more memory than free "
                     "hosting allows (~1 GB) and will crash/suspend the app. Use the "
                     "scheduled GitHub Actions job for the full scan."),
    "sp500": ("warn", "~500 stocks can approach the ~1 GB memory limit on free "
                      "hosting and may be slow. If it fails, use a smaller universe."),
    "nasdaq100": ("ok", ""),
    "dow": ("ok", ""),
}


def assess_scan_safety(
    universe: str,
    n_tickers: Optional[int] = None,
    custom_block_over: int = CUSTOM_BLOCK_OVER,
    custom_warn_over: int = CUSTOM_WARN_OVER,
) -> Tuple[str, str]:
    """Classify a scan request as ('ok'|'warn'|'block', message).

    Args:
        universe: 'all' / 'sp500' / 'nasdaq100' / 'dow' / 'custom' (others -> ok).
        n_tickers: number of tickers for a custom list.
    """
    key = (universe or "").strip().lower()

    if key == "custom":
        n = n_tickers or 0
        if n > custom_block_over:
            return ("block", f"{n} tickers is too many for free hosting (~1 GB RAM). "
                             f"Keep custom lists under {custom_block_over}.")
        if n > custom_warn_over:
            return ("warn", f"{n} tickers may be slow or memory-heavy on free hosting.")
        return ("ok", "")

    return _INDEX_LEVELS.get(key, ("ok", ""))


# Universes too large to ever run on-demand in limited hosting — the dashboard
# shows the last scheduled-run (cached) result instead of running them live.
CACHED_ONLY = {"all"}


def is_cached_only(universe: str) -> bool:
    """True if this universe must be shown from cache, never run on demand."""
    return (universe or "").strip().lower() in CACHED_ONLY
