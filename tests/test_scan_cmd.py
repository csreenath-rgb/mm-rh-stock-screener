"""TDD: testable command-builder + progress parser for dashboard scans.

The dashboard runs run_optimized_scan.py as a subprocess. Factor the exact
argv and the live-progress line parsing into pure functions so they can be
unit-tested without launching Streamlit or a real scan.
"""
import sys

import pytest

from src.screening.scan_cmd import build_scan_cmd, progress_message


# ----------------------- build_scan_cmd -----------------------

def test_named_universe_basic_shape():
    cmd = build_scan_cmd("sp500", python="py")
    assert cmd[:2] == ["py", "run_optimized_scan.py"]
    assert cmd[cmd.index("--universe") + 1] == "sp500"
    assert "--git-storage" in cmd
    # dashboard default: notifications OFF
    assert "--no-notify" in cmd
    # named universe must NOT pass --tickers
    assert "--tickers" not in cmd


def test_defaults_to_current_interpreter():
    assert build_scan_cmd("dow")[0] == sys.executable


def test_min_price_and_volume_are_stringified():
    cmd = build_scan_cmd("dow", min_price=12.5, min_volume=250000)
    assert cmd[cmd.index("--min-price") + 1] == "12.5"
    assert cmd[cmd.index("--min-volume") + 1] == "250000"


def test_speed_flags_passed_through():
    assert "--conservative" in build_scan_cmd("dow", speed_flags=["--conservative"])


def test_custom_universe_passes_tickers():
    cmd = build_scan_cmd("custom", custom_tickers="AAPL, MSFT", python="py")
    assert cmd[cmd.index("--tickers") + 1] == "AAPL, MSFT"


def test_notify_true_omits_no_notify():
    assert "--no-notify" not in build_scan_cmd("dow", notify=True)


# ----------------------- progress_message -----------------------

def test_progress_message_extracts_human_text():
    line = ("2026-06-25 14:44:15,152 - src.screening.optimized_batch_processor"
            " - INFO - Progress: 42/503 (8.3%) | Rate: 1.2/sec | ETA: 0:03:00")
    assert progress_message(line) == "42/503 (8.3%) | Rate: 1.2/sec | ETA: 0:03:00"


def test_progress_message_none_for_unrelated_line():
    assert progress_message("INFO - Analyzing AAPL...") is None


def test_progress_message_handles_trailing_newline():
    assert progress_message("... INFO - Progress: 1/10 (10.0%)\n") == "1/10 (10.0%)"
