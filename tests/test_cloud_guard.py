"""TDD: scan-size safety guard for the memory-limited (Streamlit Cloud) dashboard."""

import pytest
from src.screening import cloud_guard as g


@pytest.mark.parametrize("universe,expected", [
    ("all", "block"),
    ("sp500", "warn"),
    ("nasdaq100", "ok"),
    ("dow", "ok"),
])
def test_index_universe_levels(universe, expected):
    level, msg = g.assess_scan_safety(universe)
    assert level == expected
    if level != "ok":
        assert msg  # non-empty explanation


@pytest.mark.parametrize("n,expected", [
    (10, "ok"),
    (80, "warn"),
    (200, "block"),
])
def test_custom_list_size_levels(n, expected):
    level, msg = g.assess_scan_safety("custom", n_tickers=n)
    assert level == expected


def test_block_takes_precedence_message_mentions_memory():
    level, msg = g.assess_scan_safety("all")
    assert level == "block"
    assert "memory" in msg.lower() or "too large" in msg.lower()


def test_unknown_universe_defaults_ok():
    assert g.assess_scan_safety("weird")[0] == "ok"


def test_is_cached_only():
    assert g.is_cached_only("all") is True
    assert g.is_cached_only("ALL") is True
    assert g.is_cached_only("sp500") is False
    assert g.is_cached_only("dow") is False
    assert g.is_cached_only("custom") is False


def test_russell1000_is_cached_only_and_blocked():
    assert g.is_cached_only("russell1000") is True
    assert g.assess_scan_safety("russell1000")[0] == "block"


def test_allow_heavy_unblocks_large_universes():
    # Default: heavy universes are blocked / cached-only.
    assert g.assess_scan_safety("russell1000")[0] == "block"
    assert g.assess_scan_safety("all")[0] == "block"
    assert g.is_cached_only("russell1000") is True
    assert g.is_cached_only("all") is True
    # With allow_heavy (local/high-memory): runnable (warn) and not cached-only.
    assert g.assess_scan_safety("russell1000", allow_heavy=True)[0] == "warn"
    assert g.assess_scan_safety("all", allow_heavy=True)[0] == "warn"
    assert g.is_cached_only("russell1000", allow_heavy=True) is False
    assert g.is_cached_only("all", allow_heavy=True) is False
    # sp500 stays a warning either way; dow stays ok.
    assert g.assess_scan_safety("sp500", allow_heavy=True)[0] == "warn"
    assert g.assess_scan_safety("dow", allow_heavy=True)[0] == "ok"
