#!/usr/bin/env python3
"""Refresh the shipped index-constituent CSVs from Wikipedia.

Run on a networked machine (laptop or CI), then commit the updated CSVs:
    python scripts/refresh_universes.py

The daily scan never calls this - it only reads the committed CSVs.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.universe_refresh import refresh_all  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> int:
    try:
        results = refresh_all()
    except Exception as exc:
        logging.error("Refresh failed: %s", exc)
        return 1
    print("Updated index CSVs:")
    for name, count in results.items():
        print(f"  {name}: {count} tickers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
