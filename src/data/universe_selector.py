"""Select which set of tickers the screener scans.

Universes:
    all        - full ~3,800 US common-stock universe (USStockUniverseFetcher)
    sp500      - S&P 500 constituents      (data/universes/sp500.csv)
    nasdaq100  - Nasdaq-100 constituents   (data/universes/nasdaq100.csv)
    dow        - Dow 30 constituents       (data/universes/dow.csv)
    custom     - an explicit ticker list (--tickers "AAPL,MSFT" or --tickers-file path)

Index lists are read from shipped CSV files (one ticker per line; blank lines and
'#' comments ignored). Refresh them with scripts/refresh_universes.py. Named-index
and custom scans hit exactly those tickers (no broad-universe filtering), so you
always get the full index even if a member would be dropped by price/volume filters.
"""

import re
from pathlib import Path
from typing import List, Optional

# Default location of the shipped constituent CSVs (relative to repo root).
UNIVERSES_DIR = Path("data/universes")

INDEX_FILES = {
    "sp500": "sp500.csv",
    "nasdaq100": "nasdaq100.csv",
    "dow": "dow.csv",
}

# Order matters only for display/help.
_ALL_NAMES = ["all", "sp500", "nasdaq100", "dow", "custom"]

_SPLIT_RE = re.compile(r"[,\s]+")


def available_universes() -> List[str]:
    """Return the list of valid --universe choices."""
    return list(_ALL_NAMES)


def normalize_ticker(ticker: str) -> str:
    """Normalize a ticker for yfinance: upper-case, trimmed, '.'->'-' (BRK.B -> BRK-B)."""
    return ticker.strip().upper().replace(".", "-")


def _dedupe(tickers: List[str]) -> List[str]:
    """Drop blanks and duplicates while preserving first-seen order."""
    seen = set()
    out = []
    for t in tickers:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def parse_custom(text: str) -> List[str]:
    """Parse a custom ticker list from comma/space/newline-separated text."""
    raw = _SPLIT_RE.split(text.strip())
    return _dedupe([normalize_ticker(t) for t in raw if t.strip()])


def _read_csv_list(path: Path) -> List[str]:
    """Read tickers from a constituent CSV (first field per line; skip blanks/comments)."""
    tickers = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        first = line.split(",")[0]
        tickers.append(normalize_ticker(first))
    return _dedupe(tickers)


def get_universe(
    name: str,
    custom: Optional[str] = None,
    custom_file: Optional[str] = None,
    universes_dir: Optional[Path] = None,
    fetcher=None,
) -> List[str]:
    """Return the ticker list for the requested universe.

    Args:
        name: one of available_universes().
        custom: comma/space-separated tickers (for name='custom').
        custom_file: path to a file of tickers (for name='custom').
        universes_dir: override the CSV directory (tests inject a temp dir).
        fetcher: object with .fetch_universe() (for name='all'; injectable for tests).

    Raises:
        ValueError: unknown name, or custom with no input.
        FileNotFoundError: index CSV missing (prompt to run the refresh script).
    """
    key = (name or "").strip().lower()

    if key == "all":
        if fetcher is None:
            from src.data.universe_fetcher import USStockUniverseFetcher
            fetcher = USStockUniverseFetcher()
        return fetcher.fetch_universe()

    if key == "custom":
        if custom_file:
            text = Path(custom_file).read_text()
        elif custom:
            text = custom
        else:
            raise ValueError("custom universe requires --tickers or --tickers-file")
        tickers = parse_custom(text)
        if not tickers:
            raise ValueError("custom universe produced no tickers")
        return tickers

    if key in INDEX_FILES:
        base = Path(universes_dir) if universes_dir is not None else UNIVERSES_DIR
        path = base / INDEX_FILES[key]
        if not path.exists():
            raise FileNotFoundError(
                f"Constituent list not found: {path}. "
                f"Run: python scripts/refresh_universes.py"
            )
        tickers = _read_csv_list(path)
        if not tickers:
            raise ValueError(f"{path} contains no tickers")
        return tickers

    raise ValueError(
        f"Unknown universe '{name}'. Choices: {', '.join(_ALL_NAMES)}"
    )
