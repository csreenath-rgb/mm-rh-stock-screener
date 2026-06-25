"""TDD: structured report JSON (shared by the scanner and the dashboard)."""

import json
from src.screening import report_io


SAMPLE_RESULTS = {
    "total_processed": 30,
    "total_analyzed": 28,
    "fundamentals_unavailable": 3,
    "processing_time_seconds": 42.0,
    "actual_tps": 1.5,
    "error_rate": 0.0,
}
SAMPLE_BUYS = [
    {"ticker": "AAPL", "score": 91.0, "phase": "Phase 2", "entry_quality": "Good",
     "stop_loss": 180.0, "risk_reward_ratio": 3.0, "breakout_price": 195.0,
     "details": {"rs_slope": 0.42, "volume_ratio": 1.8}},
]
SAMPLE_SELLS = [
    {"ticker": "XYZ", "score": 75.0, "phase": "Phase 4", "details": {"rs_slope": -0.3}},
]
SAMPLE_SPY = {"phase": 2, "phase_name": "Phase 2 (Uptrend)"}
SAMPLE_BREADTH = {"phase2_pct": 41.5}


def test_build_report_dict_top_level_and_universe_label():
    d = report_io.build_report_dict(
        SAMPLE_RESULTS, SAMPLE_BUYS, SAMPLE_SELLS, SAMPLE_SPY, SAMPLE_BREADTH,
        universe_label="Dow 30",
    )
    assert d["universe"] == "Dow 30"
    assert d["stats"]["buy_count"] == 1
    assert d["stats"]["sell_count"] == 1
    assert d["stats"]["fundamentals_unavailable"] == 3
    assert d["stats"]["total_analyzed"] == 28


def test_build_report_dict_extracts_buy_signal_fields():
    d = report_io.build_report_dict(SAMPLE_RESULTS, SAMPLE_BUYS, [], SAMPLE_SPY, SAMPLE_BREADTH)
    b = d["buy_signals"][0]
    assert b["ticker"] == "AAPL"
    assert b["score"] == 91.0
    assert b["stop_loss"] == 180.0
    assert b["risk_reward_ratio"] == 3.0
    assert b["rs_slope"] == 0.42
    assert b["volume_ratio"] == 1.8


def test_build_report_dict_market_regime():
    d = report_io.build_report_dict(SAMPLE_RESULTS, [], [], SAMPLE_SPY, SAMPLE_BREADTH)
    assert d["market"]["spy_phase"] in (2, "Phase 2 (Uptrend)")
    assert d["market"]["breadth_phase2_pct"] == 41.5


def test_build_report_dict_is_json_serializable():
    d = report_io.build_report_dict(SAMPLE_RESULTS, SAMPLE_BUYS, SAMPLE_SELLS, SAMPLE_SPY, SAMPLE_BREADTH)
    json.dumps(d)  # must not raise


def test_write_and_load_report_json_roundtrip(tmp_path):
    d = report_io.build_report_dict(SAMPLE_RESULTS, SAMPLE_BUYS, SAMPLE_SELLS, SAMPLE_SPY, SAMPLE_BREADTH, universe_label="Custom")
    p = tmp_path / "scan.json"
    report_io.write_report_json(str(p), d)
    loaded = report_io.load_report_json(str(p))
    assert loaded["universe"] == "Custom"
    assert loaded["buy_signals"][0]["ticker"] == "AAPL"


def test_build_report_dict_handles_missing_optionals():
    # Sells with no details / missing fields must not crash.
    d = report_io.build_report_dict(SAMPLE_RESULTS, [], [{"ticker": "Q", "score": 60}], None, None)
    assert d["sell_signals"][0]["ticker"] == "Q"
    assert d["market"]["spy_phase"] is None
