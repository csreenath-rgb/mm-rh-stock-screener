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
    assert set(ur.EXPECTED_COUNTS) == {"sp500", "nasdaq100", "dow", "russell1000"}


def test_fetch_index_sends_user_agent_and_parses(monkeypatch):
    """fetch_index must send a User-Agent (Wikipedia 403s the default urllib UA)."""
    captured = {}

    class FakeResp:
        status_code = 200
        text = ("<table><tr><th>Symbol</th></tr>"
                "<tr><td>AAPL</td></tr><tr><td>MSFT</td></tr></table>")

        def raise_for_status(self):
            return None

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers or {}
        return FakeResp()

    monkeypatch.setattr(ur.requests, "get", fake_get)
    out = ur.fetch_index("dow")
    assert out == ["AAPL", "MSFT"]
    assert captured["headers"].get("User-Agent")  # non-empty UA sent
    assert captured["url"] == ur.SOURCES["dow"][1]


ISHARES_CSV = '''iShares Russell 1000 ETF
Fund Holdings as of,"Jun 24, 2026"
 ,
Ticker,Name,Sector,Asset Class,Weight (%)
"AAPL","APPLE INC","Information Technology","Equity","6.5"
"MSFT","MICROSOFT CORP","Information Technology","Equity","6.0"
"BRKB","BERKSHIRE HATHAWAY INC CLASS B","Financials","Equity","1.5"
"USD","US DOLLAR","Cash and/or Derivatives","Cash","0.1"
'''


def test_extract_ishares_symbols_filters_cash_and_fixes_class_shares():
    out = ur.extract_ishares_symbols(ISHARES_CSV)
    assert out == ["AAPL", "MSFT", "BRK-B"]   # cash row dropped, BRKB -> BRK-B


def test_russell1000_in_expected_counts():
    assert "russell1000" in ur.EXPECTED_COUNTS


def test_refresh_all_isolates_per_index_failures(tmp_path, monkeypatch):
    # sp500/nasdaq100/dow succeed; russell1000 (iShares) raises — others must still write.
    good = {"sp500": ["T%d" % i for i in range(500)],
            "nasdaq100": ["N%d" % i for i in range(100)],
            "dow": ["D%d" % i for i in range(30)]}

    def fake_fetch(name, timeout=30):
        if name == "russell1000":
            raise RuntimeError("iShares 403")
        return good[name]

    monkeypatch.setattr(ur, "fetch_index", fake_fetch)
    results = ur.refresh_all(universes_dir=tmp_path)

    assert results["sp500"] == 500 and results["dow"] == 30
    assert isinstance(results["russell1000"], str) and "FAIL" in results["russell1000"].upper()
    assert (tmp_path / "sp500.csv").exists() and (tmp_path / "dow.csv").exists()
    assert not (tmp_path / "russell1000.csv").exists()


def test_fetch_russell1000_reads_local_ishares_file(tmp_path, monkeypatch):
    f = tmp_path / "IWB_holdings.csv"
    f.write_text(ISHARES_CSV)
    monkeypatch.setitem(ur.SOURCES, "russell1000", ("ishares_local", str(f)))
    assert ur.fetch_index("russell1000") == ["AAPL", "MSFT", "BRK-B"]


def test_fetch_russell1000_missing_local_file_raises(tmp_path, monkeypatch):
    monkeypatch.setitem(ur.SOURCES, "russell1000", ("ishares_local", str(tmp_path / "nope.csv")))
    with pytest.raises(FileNotFoundError):
        ur.fetch_index("russell1000")
