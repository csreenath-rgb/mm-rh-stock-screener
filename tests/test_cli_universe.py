"""TDD: --universe / --tickers / --tickers-file wiring in run_optimized_scan."""

import pytest
import run_optimized_scan as ros


def test_parser_universe_defaults_to_all():
    assert ros.build_parser().parse_args([]).universe == "all"


def test_parser_accepts_each_index_choice():
    for u in ("all", "sp500", "nasdaq100", "dow", "custom"):
        assert ros.build_parser().parse_args(["--universe", u]).universe == u


def test_parser_rejects_unknown_universe():
    with pytest.raises(SystemExit):
        ros.build_parser().parse_args(["--universe", "russell2000"])


def test_parser_tickers_and_tickers_file():
    a = ros.build_parser().parse_args(["--universe", "custom", "--tickers", "AAPL,MSFT"])
    assert a.tickers == "AAPL,MSFT"
    a2 = ros.build_parser().parse_args(["--tickers-file", "watch.txt"])
    assert a2.tickers_file == "watch.txt"


def test_resolve_universe_custom_returns_tickers_and_label():
    a = ros.build_parser().parse_args(["--universe", "custom", "--tickers", "aapl, msft"])
    tickers, label = ros.resolve_universe(a)
    assert tickers == ["AAPL", "MSFT"]
    assert "ustom" in label  # "Custom ..." human label


def test_universe_labels_cover_all_choices():
    for u in ("all", "sp500", "nasdaq100", "dow", "custom"):
        assert u in ros.UNIVERSE_LABELS


def test_resolve_universe_test_mode_truncates(monkeypatch):
    # Build a custom universe of 5, with --test-mode capping at 100 (no truncation here),
    # then a larger one to confirm capping logic via the helper.
    a = ros.build_parser().parse_args(["--universe", "custom",
                                       "--tickers", ",".join(f"T{i}" for i in range(150)),
                                       "--test-mode"])
    tickers, _ = ros.resolve_universe(a)
    assert len(tickers) == 100  # test-mode caps at 100
