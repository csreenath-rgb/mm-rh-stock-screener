# Universe Selection & Dashboard

You can now choose **which set of stocks** the screener scans, and view results in a
web dashboard instead of only a text file.

## Universes

| Universe | Tickers | Source | Typical runtime (conservative) |
| --- | --- | --- | --- |
| `all` | ~3,800 | live exchange listings | ~30–40 min |
| `sp500` | ~500 | `data/universes/sp500.csv` | a few minutes |
| `nasdaq100` | ~100 | `data/universes/nasdaq100.csv` | ~1 min |
| `dow` | 30 | `data/universes/dow.csv` | seconds |
| `custom` | your list | `--tickers` / `--tickers-file` | depends |

> Note: the `all` universe already **contains** every S&P 500 / Nasdaq-100 / Dow
> member, so picking an index doesn't scan stocks you'd otherwise miss — it scans a
> faster, focused subset. A named index or custom list is scanned **directly** (the
> broad price/volume filter is not applied), so you always get the full index.

## One-time setup: populate the index lists

The index CSVs are generated from the public Wikipedia constituent tables. Run this
once on a networked machine (and re-run occasionally as indices change), then commit
the updated CSVs:

```bash
python scripts/refresh_universes.py
```

It validates the counts (≈500 / ≈100 / 30) before overwriting, so a bad fetch can't
corrupt the lists. The daily scan never calls this — it only reads the committed CSVs.
(`custom` lists need no setup.)

## Command line

```bash
# Focused index scans
python run_optimized_scan.py --universe dow --git-storage
python run_optimized_scan.py --universe sp500 --git-storage --conservative

# Your own watchlist
python run_optimized_scan.py --universe custom --tickers "AAPL,MSFT,NVDA" --git-storage
python run_optimized_scan.py --universe custom --tickers-file watchlist.txt --git-storage

# Full market (the scheduled default)
python run_optimized_scan.py --universe all --git-storage --conservative
```

Each run writes both `data/daily_scans/latest_optimized_scan.txt` and
`latest_optimized_scan.json` (the dashboard reads the JSON), and labels the report
with the universe scanned.

## Dashboard

Pick a universe, run a scan, and view ranked buy/sell signals + market regime.

```bash
# Local
pip install -r requirements-dashboard.txt
streamlit run dashboard/app.py

# Docker
docker compose up dashboard      # then open http://localhost:8501
```

Notifications are **off by default** in the dashboard (interactive runs shouldn't spam
your email/Telegram); tick the box under Advanced to enable them for a run. Use the
**History** dropdown to re-open past scans.

> The full `all` scan takes 30–40 min and is best left to the scheduled GitHub Actions
> job; the dashboard is ideal for the fast index/custom universes.

## GitHub Actions

Manually triggering the workflow now offers a **universe** dropdown
(all / sp500 / nasdaq100 / dow). The scheduled daily run stays on `all`.

## Russell 1000

Russell 1000 (`--universe russell1000`, ~1,000 stocks) is sourced from the **iShares
Russell 1000 ETF (IWB) holdings CSV** (Wikipedia doesn't list its constituents), via
the same `scripts/refresh_universes.py` / refresh workflow. A few class-share tickers
(e.g. `BRKB`→`BRK-B`) are reconciled to yfinance format; add more in
`ISHARES_FIXUPS` if needed.

Because ~1,000 stocks exceed the free Streamlit Cloud memory limit, Russell 1000
(like **All US stocks**) is **cached-only** in the dashboard: it shows the most recent
scheduled/dispatched scan (committed `data/daily_scans/latest_russell1000.json`) with a
bold "cached — not on-demand" disclaimer, and never runs live. To refresh its cached
result, trigger the daily workflow with `universe = russell1000`.
