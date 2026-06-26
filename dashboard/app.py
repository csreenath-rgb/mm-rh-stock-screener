"""Streamlit dashboard for the MM-RH stock screener.

Pick a universe (S&P 500 / Nasdaq-100 / Dow 30 / custom list), run a scan, and
view ranked buy/sell signals with market regime. Runs the existing
run_optimized_scan.py as a subprocess and renders its structured JSON output.

Run locally:   streamlit run dashboard/app.py
Run in Docker: docker compose up dashboard   (then open http://localhost:8501)
"""

import subprocess
import sys
from pathlib import Path

import streamlit as st

# Make the repo root importable and the working dir for the scan subprocess.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.screening import report_io  # noqa: E402
from src.screening.cloud_guard import assess_scan_safety, is_cached_only  # noqa: E402
from src.screening.scan_cmd import build_scan_cmd, progress_message  # noqa: E402
from src.screening.dashboard_view import signals_dataframe, apply_sort  # noqa: E402
from src.data import universe_selector  # noqa: E402

DAILY_SCANS = REPO_ROOT / "data" / "daily_scans"
LATEST_JSON = DAILY_SCANS / "latest_optimized_scan.json"

UNIVERSE_CHOICES = {
    "S&P 500": "sp500",
    "Nasdaq-100": "nasdaq100",
    "Dow 30": "dow",
    "All US stocks (CACHED daily result — not on-demand)": "all",
    "Russell 1000 (CACHED — not on-demand)": "russell1000",
    "Custom list": "custom",
}
SPEED_FLAGS = {
    "Conservative (safe)": ["--conservative"],
    "Default": [],
    "Aggressive (may hit rate limits)": ["--aggressive"],
}

st.set_page_config(page_title="MM-RH Stock Screener", layout="wide")
st.title("📈 MM-RH Stock Screener")


def run_scan(universe, tickers, speed_flags, min_price, min_volume, notify, status_box=None):
    """Run the scan as a subprocess, streaming live progress to ``status_box``.

    Returns ``(returncode, tail)`` where ``tail`` is the last chunk of output
    (for error display). The scan logs ``Progress: X/N ...`` lines as it works;
    we surface them live so a long scan never looks frozen. stdout+stderr are
    merged so a single reader catches the progress lines (which go to stderr).
    """
    cmd = build_scan_cmd(universe, tickers, speed_flags, min_price, min_volume, notify)
    proc = subprocess.Popen(
        cmd, cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    lines = []
    for line in proc.stdout:
        lines.append(line)
        msg = progress_message(line)
        if msg and status_box is not None:
            status_box.caption(f"\u23f3 Progress: {msg}")
    proc.wait()
    return proc.returncode, "".join(lines[-60:])


def render_report(report):
    if not report:
        st.info("No scan loaded yet. Pick a universe and click **Run scan**.")
        return
    st.subheader(f"{report.get('universe') or 'Scan'} — {report.get('scan_date', '')}")
    stats = report.get("stats", {})
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Analyzed", stats.get("total_analyzed"))
    c2.metric("Buy signals", stats.get("buy_count"))
    c3.metric("Sell signals", stats.get("sell_count"))
    c4.metric("Fundamentals N/A", stats.get("fundamentals_unavailable"))
    err = stats.get("error_rate")
    c5.metric("Error rate", f"{err*100:.1f}%" if isinstance(err, (int, float)) else "—")

    market = report.get("market", {})
    st.caption(f"Market: SPY {market.get('spy_phase')} · Breadth (Phase 2) "
               f"{market.get('breadth_phase2_pct')}%")

    buys = report.get("buy_signals", [])
    sells = report.get("sell_signals", [])
    buy_df = signals_dataframe(buys)
    sell_df = signals_dataframe(sells)

    # Sort controls applied to both tables. Default: Score, highest first.
    sort_cols = list(buy_df.columns) or list(sell_df.columns)
    if sort_cols:
        sc1, sc2 = st.columns([3, 1])
        default_ix = sort_cols.index("Score") if "Score" in sort_cols else 0
        sort_by = sc1.selectbox("Sort results by", sort_cols, index=default_ix)
        ascending = sc2.radio("Order", ["Descending", "Ascending"], horizontal=True) == "Ascending"
        buy_df = apply_sort(buy_df, sort_by, ascending)
        sell_df = apply_sort(sell_df, sort_by, ascending)

    st.markdown("### 🟢 Buy signals")
    if not buy_df.empty:
        st.dataframe(buy_df, use_container_width=True, hide_index=True)
    else:
        st.write("None")

    st.markdown("### 🔴 Sell signals")
    if not sell_df.empty:
        st.dataframe(sell_df, use_container_width=True, hide_index=True)
    else:
        st.write("None")


# ---------------- Sidebar controls ----------------
with st.sidebar:
    st.header("Scan settings")
    label = st.radio("Universe", list(UNIVERSE_CHOICES.keys()))
    universe = UNIVERSE_CHOICES[label]
    custom_tickers = ""
    if universe == "custom":
        custom_tickers = st.text_area("Tickers (comma/space separated)", "AAPL, MSFT, NVDA")
    speed = st.selectbox("Scan speed", list(SPEED_FLAGS.keys()))
    with st.expander("Advanced"):
        min_price = st.number_input("Min price", value=5.0, step=1.0)
        min_volume = st.number_input("Min volume", value=100000, step=10000)
        notify = st.checkbox("Send email/Telegram alerts", value=False)
        allow_heavy = st.checkbox(
            "Allow heavy scans (All / Russell 1000)",
            value=False,
            help="Enable only on a high-memory host (local / your own server). "
                 "These need lots of RAM and several minutes; they will crash free Cloud hosting.",
        )

    # Memory-safety guard for limited hosting (e.g. Streamlit Cloud ~1 GB RAM)
    n_custom = len(universe_selector.parse_custom(custom_tickers)) if universe == "custom" else None
    safety_level, safety_msg = assess_scan_safety(universe, n_custom, allow_heavy=allow_heavy)
    if safety_level == "block":
        st.error(safety_msg)
    elif safety_level == "warn":
        st.warning(safety_msg)
    run_clicked = st.button("▶ Run scan", type="primary", disabled=(safety_level == "block"))

    st.divider()
    history = report_io.list_report_files(str(DAILY_SCANS))
    hist_choice = st.selectbox("History", ["(latest)"] + history, format_func=lambda p: p.split("/")[-1].split("\\")[-1])

# ---------------- Main panel ----------------
cached_only = is_cached_only(universe, allow_heavy=allow_heavy)

if cached_only:
    st.markdown(
        "> ### ⚠️ CACHED RESULT — NOT run on demand\n"
        "> **This is the most recent _scheduled_ full-market scan committed by the daily job.** "
        "The full ~3,800-stock universe is **not available to run live here** (memory limits) — "
        "it refreshes only when the scheduled GitHub Actions job runs."
    )
elif run_clicked and safety_level != "block":
    status_box = st.empty()
    with st.spinner(f"Scanning {label}… live progress below"):
        returncode, tail = run_scan(
            universe, custom_tickers, SPEED_FLAGS[speed],
            min_price, min_volume, notify, status_box=status_box,
        )
    if returncode != 0:
        st.error("Scan failed. Last lines of output:")
        st.code(tail[-3000:])
    else:
        status_box.empty()
        st.success("Scan complete.")

# Decide which report to show
report = None
try:
    if cached_only:
        # Show ONLY this universe's own cached file — never a different universe's scan.
        cached_file = DAILY_SCANS / f"latest_{universe}.json"
        report = report_io.load_report_json(str(cached_file)) if cached_file.exists() else None
        if report is None:
            st.info(f"No cached **{label}** scan yet. Trigger the daily GitHub Actions "
                    f"workflow with universe = `{universe}` to populate it.")
    elif hist_choice and hist_choice != "(latest)":
        report = report_io.load_report_json(hist_choice)
    elif LATEST_JSON.exists():
        report = report_io.load_report_json(str(LATEST_JSON))
except Exception as e:
    st.warning(f"Could not load report: {e}")

if cached_only and report:
    st.markdown(f"**🕒 Cached version generated:** {report.get('generated_at', '?')} "
                f"(scanned universe: {report.get('universe', '?')})")

# Assigning the result prevents Streamlit's "magic" from auto-printing it.
_ = render_report(report)
