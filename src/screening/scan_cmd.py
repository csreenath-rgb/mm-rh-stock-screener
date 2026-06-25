"""Build the argv for a screener scan subprocess, and parse its progress lines.

Factored out of the Streamlit dashboard so the exact command and the
live-progress parsing can be unit-tested without launching Streamlit or
running a real scan. Keeping these as pure functions is what lets the
dashboard stream progress (instead of blocking on capture_output) safely.
"""
from __future__ import annotations

import sys
from typing import List, Optional, Sequence


def build_scan_cmd(
    universe: str,
    custom_tickers: str = "",
    speed_flags: Optional[Sequence[str]] = None,
    min_price: float = 5.0,
    min_volume: int = 100000,
    notify: bool = False,
    python: Optional[str] = None,
) -> List[str]:
    """Return the argv list that runs run_optimized_scan.py for one scan.

    `python` defaults to the current interpreter (sys.executable).
    For ``universe == "custom"`` the tickers are passed via ``--tickers``.
    ``notify=False`` (the dashboard default) appends ``--no-notify``.
    The flag order mirrors the dashboard's original inline command so
    behaviour is unchanged.
    """
    py = python or sys.executable
    cmd: List[str] = [
        py, "run_optimized_scan.py",
        "--universe", universe,
        "--git-storage",
        "--min-price", str(min_price),
        "--min-volume", str(min_volume),
    ]
    cmd += list(speed_flags or [])
    if universe == "custom":
        cmd += ["--tickers", custom_tickers]
    if not notify:
        cmd += ["--no-notify"]
    return cmd


def progress_message(line: str) -> Optional[str]:
    """Extract the human-readable progress text from one scan log line.

    The scan logs lines like
    ``... - INFO - Progress: 42/503 (8.3%) | Rate: 1.2/sec | ETA: 0:03:00``.
    Returns the text after ``Progress:`` (stripped), or None for any line
    that is not a progress update.
    """
    marker = "Progress:"
    if marker not in line:
        return None
    return line.split(marker, 1)[1].strip()
