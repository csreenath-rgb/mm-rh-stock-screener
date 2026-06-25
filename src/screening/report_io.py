"""Structured (JSON) representation of a scan, shared by the scanner and dashboard.

The scanner writes data/daily_scans/latest_optimized_scan.json alongside the .txt
report; the Streamlit dashboard reads it back to render sortable tables without
parsing free text. All extraction is defensive so missing fields never crash.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional


def _num(v):
    """Return v if it is a real number, else None (keeps JSON clean)."""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _signal_row(sig: Dict) -> Dict:
    details = sig.get("details", {}) or {}
    return {
        "ticker": sig.get("ticker"),
        "score": _num(sig.get("score")),
        "phase": sig.get("phase"),
        "current_price": (round(cp, 2) if isinstance((cp := sig.get("current_price")), (int, float)) and not isinstance(cp, bool) else None),
        "stop_loss": _num(sig.get("stop_loss")),
        # Exit/profit target: buy signals carry details.reward_target.
        "target_price": _num(details.get("reward_target")),
        "risk_reward_ratio": _num(sig.get("risk_reward_ratio")),
        "entry_quality": sig.get("entry_quality"),
        "breakout_price": _num(sig.get("breakout_price")),
        "rs_slope": _num(details.get("rs_slope")),
        "volume_ratio": _num(details.get("volume_ratio")),
    }


def build_report_dict(
    results: Dict,
    buy_signals: List[Dict],
    sell_signals: List[Dict],
    spy_analysis: Optional[Dict],
    breadth: Optional[Dict],
    universe_label: Optional[str] = None,
) -> Dict:
    """Build a JSON-serializable summary of a scan."""
    results = results or {}
    spy_analysis = spy_analysis or {}
    breadth = breadth or {}

    spy_phase = spy_analysis.get("phase_name") or spy_analysis.get("phase")

    return {
        "scan_date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "universe": universe_label,
        "stats": {
            "total_processed": results.get("total_processed"),
            "total_analyzed": results.get("total_analyzed"),
            "fundamentals_unavailable": results.get("fundamentals_unavailable"),
            "processing_time_seconds": _num(results.get("processing_time_seconds")),
            "actual_tps": _num(results.get("actual_tps")),
            "error_rate": _num(results.get("error_rate")),
            "buy_count": len(buy_signals or []),
            "sell_count": len(sell_signals or []),
        },
        "market": {
            "spy_phase": spy_phase,
            "breadth_phase2_pct": _num(breadth.get("phase2_pct")),
        },
        "buy_signals": [_signal_row(s) for s in (buy_signals or [])],
        "sell_signals": [_signal_row(s) for s in (sell_signals or [])],
    }


def write_report_json(path: str, report_dict: Dict) -> None:
    """Write the report dict to path as pretty JSON."""
    with open(path, "w") as f:
        json.dump(report_dict, f, indent=2, default=str)


def load_report_json(path: str) -> Dict:
    """Load a report dict previously written by write_report_json."""
    with open(path) as f:
        return json.load(f)


def list_report_files(dirpath: str) -> List[str]:
    """Return timestamped scan-report JSON paths, newest first.

    Excludes 'latest_optimized_scan.json' and non-JSON files. Returns [] if the
    directory does not exist.
    """
    import os
    if not os.path.isdir(dirpath):
        return []
    names = [
        n for n in os.listdir(dirpath)
        if n.startswith("optimized_scan_") and n.endswith(".json")
    ]
    names.sort(reverse=True)  # timestamp in name -> lexical sort = chronological
    return [os.path.join(dirpath, n) for n in names]


def prune_reports(dirpath: str, keep: int) -> List[str]:
    """Keep only the newest `keep` timestamped scan reports; delete older ones.

    Deletes both the .json and .txt for each pruned timestamp. Never touches
    latest_optimized_scan.*. Returns the list of deleted file paths. Safe if the
    directory is missing or has fewer than `keep` reports.
    """
    import os
    if keep is None or keep < 0 or not os.path.isdir(dirpath):
        return []
    stamps = sorted(
        {n[len("optimized_scan_"):-len(".json")]
         for n in os.listdir(dirpath)
         if n.startswith("optimized_scan_") and n.endswith(".json")},
        reverse=True,
    )
    deleted = []
    for ts in stamps[keep:]:
        for ext in (".json", ".txt"):
            f = os.path.join(dirpath, f"optimized_scan_{ts}{ext}")
            if os.path.exists(f):
                try:
                    os.remove(f)
                    deleted.append(f)
                except OSError:
                    pass
    return deleted
