"""TDD: parsing/validation logic for the index-constituent refresh (no network)."""

import pandas as pd
import pytest
from src.data import universe_refresh as ur
from src.data import universe_selector as us


def test_extract_symbols_from_symbol_column_normalizes():
    df = pd.DataFrame({"Symbol": ["AAPL", "MSFT", "BRK.B"], "Name": ["a", "b", "c"]})
    assert ur.extract_symbols([df]) == ["AAPL", "MSFT", "BRK-B"]


def test_extract_symbols_handles_ticker_column():
    df = pd.DataFrame({"Company": ["x"], "Ticker": ["NVDA"]})
    assert ur.extract_symbols([df]) == ["NVDA"]


def test_extract_symbols_picks_table_with_symbols_among_many():
    junk = pd.DataFrame({"Foo": [1, 2], "Bar": [3, 4]})
    good = pd.DataFrame({"Symbol": ["AAPL", "AMZN"]})
    assert ur.extract_symbols([junk, good]) == ["AAPL", "AMZN"]


def test_extract_symbols_dedupes_preserving_order():
    df = pd.DataFrame({"Symbol": ["AAPL", "MSFT", "AAPL"]})
    assert ur.extract_symbols([df]) == ["AAPL", "MSFT"]


def test_extract_symbols_raises_when_no_symbol_column():
    with pytest.raises(ValueError):
        ur.extract_symbols([pd.DataFrame({"Foo": [1], "Bar": [2]})])


def test_count_ok_ranges():
    assert ur.count_ok("dow", 30) is True
    assert ur.count_ok("dow", 12) is False
    assert ur.count_ok("sp500", 503) is True
    assert ur.count_ok("sp500", 50) is False
    assert ur.count_ok("nasdaq100", 101) is True


def test_write_universe_csv_roundtrips_through_selector(tmp_path):
    ur.write_universe_csv("dow", ["AAPL", "MSFT", "BRK-B"], universes_dir=tmp_path)
    assert us.get_universe("dow", universes_dir=tmp_path) == ["AAPL", "MSFT", "BRK-B"]


def test_expected_indices_known():
    assert set(ur.EXPECTED_COUNTS) == {"sp500", "nasdaq100", "dow"}
