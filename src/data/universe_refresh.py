"""Refresh shipped index-constituent CSVs (S&P 500, Nasdaq-100, Dow 30).

The parse/validate/write logic here is network-free and unit-tested. The live
fetch (fetch_index) reads the public Wikipedia constituent tables via
pandas.read_html and is meant to run on a networked machine (your laptop or CI),
not unattended in the daily job. The daily scan only ever reads the committed CSVs.
"""

import io
import logging
from pathlib import Path

import requests
from typing import List, Optional

from src.data.universe_selector import UNIVERSES_DIR, INDEX_FILES, normalize_ticker, _dedupe

logger = logging.getLogger(__name__)

# Wikipedia sources and the column that holds the ticker.
SOURCES = {
    "sp500": ("wikipedia", "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"),
    "nasdaq100": ("wikipedia", "https://en.wikipedia.org/wiki/Nasdaq-100"),
    "dow": ("wikipedia", "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"),
    "russell1000": ("ishares", "https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/1467271812596.ajax?fileType=csv&fileName=IWB_holdings&dataType=fund"),
}

# iShares uses class-share tickers like BRKB; map the common ones to yfinance form.
ISHARES_FIXUPS = {"BRKB": "BRK-B", "BFB": "BF-B"}

# Candidate column names that hold tickers, in priority order.
SYMBOL_COLUMNS = ("Symbol", "Ticker", "Ticker symbol")

# Sanity-check ranges so a malformed fetch never overwrites a good CSV.
EXPECTED_COUNTS = {
    "sp500": (480, 520),
    "nasdaq100": (90, 110),
    "dow": (28, 32),
    "russell1000": (950, 1050),
}


def _find_symbol_column(df):
    for col in df.columns:
        if str(col) in SYMBOL_COLUMNS:
            return col
    return None


def extract_symbols(tables: List) -> List[str]:
    """Extract normalized tickers from the first table that has a symbol column.

    Args:
        tables: list of DataFrames (e.g. from pandas.read_html).

    Returns:
        Deduped, normalized ticker list.

    Raises:
        ValueError: if no table has a recognizable symbol column.
    """
    for df in tables:
        col = _find_symbol_column(df)
        if col is not None:
            symbols = [normalize_ticker(str(v)) for v in df[col].tolist() if str(v).strip()]
            return _dedupe(symbols)
    raise ValueError(
        f"No symbol column found (looked for {SYMBOL_COLUMNS}) in any provided table"
    )


def extract_ishares_symbols(csv_text: str) -> List[str]:
    """Parse tickers from an iShares ETF holdings CSV (skips metadata + cash rows)."""
    import csv as _csv
    lines = csv_text.splitlines()
    header_idx = next((i for i, ln in enumerate(lines)
                       if "Ticker" in next(_csv.reader([ln]), [])), None)
    if header_idx is None:
        raise ValueError("iShares CSV: no Ticker header row found")
    rows = list(_csv.DictReader(lines[header_idx:]))
    out = []
    for r in rows:
        if (r.get("Asset Class") or "Equity").strip() != "Equity":
            continue
        t = normalize_ticker(str(r.get("Ticker", "")))
        t = ISHARES_FIXUPS.get(t, t)
        if t and t not in ("-", "CASH"):
            out.append(t)
    return _dedupe(out)


def count_ok(name: str, n: int) -> bool:
    """True if n is within the sane range for the given index."""
    lo, hi = EXPECTED_COUNTS[name]
    return lo <= n <= hi


# Wikipedia returns HTTP 403 to the default urllib User-Agent that pandas.read_html
# uses, so we fetch with requests + a descriptive UA and parse the returned HTML.
USER_AGENT = (
    "mm-rh-stock-screener/1.0 (https://github.com/csreenath-rgb/mm-rh-stock-screener) "
    "python-requests"
)


def fetch_index(name: str, timeout: int = 30) -> List[str]:
    """Live-fetch constituents for an index (needs network).

    Wikipedia sources are parsed as HTML tables; the Russell 1000 comes from the
    iShares IWB ETF holdings CSV. A descriptive User-Agent is sent either way
    (Wikipedia 403s the default urllib UA).
    """
    import pandas as pd
    kind, url = SOURCES[name]
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    if kind == "ishares":
        return extract_ishares_symbols(resp.text)
    tables = pd.read_html(io.StringIO(resp.text))
    return extract_symbols(tables)


def write_universe_csv(name: str, tickers: List[str], universes_dir: Optional[Path] = None) -> Path:
    """Write the ticker list to data/universes/<name>.csv (one per line)."""
    base = Path(universes_dir) if universes_dir is not None else UNIVERSES_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / INDEX_FILES[name]
    header = f"# {name} constituents - refreshed by scripts/refresh_universes.py\n"
    path.write_text(header + "\n".join(tickers) + "\n")
    return path


def refresh_all(universes_dir: Optional[Path] = None) -> dict:
    """Fetch, validate, and write each index CSV, isolating per-index failures.

    A failure for one index (e.g. iShares for Russell 1000) does not abort the
    others. Returns {name: count_int OR "FAILED: ..."}. Raises only if every
    index failed.
    """
    results = {}
    for name in SOURCES:
        try:
            tickers = fetch_index(name)
            if not count_ok(name, len(tickers)):
                results[name] = (f"FAILED: got {len(tickers)} tickers, outside "
                                 f"expected {EXPECTED_COUNTS[name]} - not written")
                logger.error("%s: %s", name, results[name])
                continue
            write_universe_csv(name, tickers, universes_dir=universes_dir)
            results[name] = len(tickers)
            logger.info("%s: wrote %d tickers", name, len(tickers))
        except Exception as e:  # one bad source must not break the others
            results[name] = f"FAILED: {e}"
            logger.error("%s refresh failed: %s", name, e)
    if all(isinstance(v, str) for v in results.values()):
        raise RuntimeError(f"All index refreshes failed: {results}")
    return results
