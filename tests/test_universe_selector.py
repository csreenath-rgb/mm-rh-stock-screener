"""TDD: universe selection (sp500 / nasdaq100 / dow / custom / all)."""

import pytest
from src.data import universe_selector as us


# ---------- ticker normalization ----------

def test_normalize_ticker_dot_to_dash_and_upper():
    assert us.normalize_ticker("brk.b") == "BRK-B"
    assert us.normalize_ticker("  aapl ") == "AAPL"
    assert us.normalize_ticker("BF.B") == "BF-B"


# ---------- custom list parsing ----------

def test_parse_custom_comma_separated():
    assert us.parse_custom("AAPL, msft ,GOOGL") == ["AAPL", "MSFT", "GOOGL"]


def test_parse_custom_mixed_whitespace_and_newlines_dedupes():
    assert us.parse_custom("AAPL msft\nGOOGL,AAPL") == ["AAPL", "MSFT", "GOOGL"]


def test_parse_custom_empty_returns_empty():
    assert us.parse_custom("   ") == []


# ---------- index CSV reading ----------

def _write_csv(p, lines):
    p.write_text("\n".join(lines) + "\n")


def test_get_universe_index_reads_csv(tmp_path):
    _write_csv(tmp_path / "dow.csv", ["# header comment", "AAPL", "msft", "", "brk.b"])
    out = us.get_universe("dow", universes_dir=tmp_path)
    assert out == ["AAPL", "MSFT", "BRK-B"]


def test_get_universe_unknown_name_raises(tmp_path):
    with pytest.raises(ValueError):
        us.get_universe("russell2000", universes_dir=tmp_path)


def test_get_universe_missing_csv_raises_helpful(tmp_path):
    with pytest.raises(FileNotFoundError):
        us.get_universe("sp500", universes_dir=tmp_path)


# ---------- custom via get_universe ----------

def test_get_universe_custom_from_string():
    assert us.get_universe("custom", custom="AAPL,MSFT") == ["AAPL", "MSFT"]


def test_get_universe_custom_from_file(tmp_path):
    f = tmp_path / "watch.txt"
    f.write_text("NVDA\nAMD\n")
    assert us.get_universe("custom", custom_file=str(f)) == ["NVDA", "AMD"]


def test_get_universe_custom_without_input_raises():
    with pytest.raises(ValueError):
        us.get_universe("custom")


# ---------- all -> delegates to the existing fetcher (injected) ----------

def test_get_universe_all_uses_injected_fetcher():
    class FakeFetcher:
        def fetch_universe(self):
            return ["AAA", "BBB", "CCC"]
    assert us.get_universe("all", fetcher=FakeFetcher()) == ["AAA", "BBB", "CCC"]


# ---------- list of valid names is discoverable ----------

def test_available_universes_lists_all_choices():
    names = set(us.available_universes())
    assert {"all", "sp500", "nasdaq100", "dow", "custom"} <= names
