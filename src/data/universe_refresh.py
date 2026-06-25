"""Refresh shipped index-constituent CSVs (S&P 500, Nasdaq-100, Dow 30).

The parse/validate/write logic here is network-free and unit-tested. The live
fetch (fetch_index) reads the public Wikipedia constituent tables via
pandas.read_html and is meant to run on a networked machine (your laptop or CI),
not unattended in the daily job. The daily scan only ever reads the committed CSVs.
"""

import logging
from pathlib import Path
from typing import List, Optional

from src.data.universe_selector import UNIVERSES_DIR, INDEX_FILES, normalize_ticker, _dedupe

logger = logging.getLogger(__name__)

# Wikipedia sources and the column that holds the ticker.
SOURCES = {
    "sp500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "nasdaq100": "https://en.wikipedia.org/wiki/Nasdaq-100",
    "dow": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
}

# Candidate column names that hold tickers, in priority order.
SYMBOL_COLUMNS = ("Symbol", "Ticker", "Ticker symbol")

# Sanity-check ranges so a malformed fetch never overwrites a good CSV.
EXPECTED_COUNTS = {
    "sp500": (480, 520),
    "nasdaq100": (90, 110),
    "dow": (28, 32),
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


def count_ok(name: str, n: int) -> bool:
    """True if n is within the sane range for the given index."""
    lo, hi = EXPECTED_COUNTS[name]
    return lo <= n <= hi


def fetch_index(name: str) -> List[str]:
    """Live-fetch constituents for an index from Wikipedia (needs network)."""
    import pandas as pd
    tables = pd.read_html(SOURCES[name])
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
    """Fetch, validate, and write all three index CSVs. Returns {name: count}."""
    results = {}
    for name in SOURCES:
        tickers = fetch_index(name)
        if not count_ok(name, len(tickers)):
            raise ValueError(
                f"{name}: got {len(tickers)} tickers, outside expected "
                f"{EXPECTED_COUNTS[name]} - refusing to overwrite CSV"
            )
        write_universe_csv(name, tickers, universes_dir=universes_dir)
        results[name] = len(tickers)
        logger.info("%s: wrote %d tickers", name, len(tickers))
    return results
