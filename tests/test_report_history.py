"""TDD: listing past scan reports for the dashboard history view."""

from src.screening import report_io


def test_list_report_files_newest_first_excluding_latest(tmp_path):
    for name in ["optimized_scan_20260101_090000.json",
                 "optimized_scan_20260102_090000.json",
                 "optimized_scan_20260103_090000.json",
                 "latest_optimized_scan.json",
                 "optimized_scan_20260101_090000.txt"]:
        (tmp_path / name).write_text("{}")
    files = report_io.list_report_files(str(tmp_path))
    names = [f.split("/")[-1].split("\\")[-1] for f in files]
    assert names == [
        "optimized_scan_20260103_090000.json",
        "optimized_scan_20260102_090000.json",
        "optimized_scan_20260101_090000.json",
    ]  # newest first, no 'latest', no .txt


def test_list_report_files_empty_dir(tmp_path):
    assert report_io.list_report_files(str(tmp_path)) == []


def test_list_report_files_missing_dir():
    assert report_io.list_report_files("/no/such/dir") == []


# ---------------- retention cap (ring buffer) ----------------

def _mk(dirp, ts):
    (dirp / f"optimized_scan_{ts}.json").write_text("{}")
    (dirp / f"optimized_scan_{ts}.txt").write_text("x")


def test_prune_reports_keeps_newest_n_deletes_older(tmp_path):
    for ts in ["20260101_090000", "20260102_090000", "20260103_090000",
               "20260104_090000", "20260105_090000"]:
        _mk(tmp_path, ts)
    (tmp_path / "latest_optimized_scan.json").write_text("{}")
    (tmp_path / "latest_optimized_scan.txt").write_text("x")

    deleted = report_io.prune_reports(str(tmp_path), keep=2)

    remaining = sorted(p.name for p in tmp_path.iterdir())
    # newest 2 timestamps (04, 05) kept (json+txt), plus latest_* untouched
    assert "optimized_scan_20260105_090000.json" in remaining
    assert "optimized_scan_20260104_090000.json" in remaining
    assert "optimized_scan_20260103_090000.json" not in remaining
    assert "optimized_scan_20260101_090000.txt" not in remaining
    assert "latest_optimized_scan.json" in remaining
    assert "latest_optimized_scan.txt" in remaining
    assert len(deleted) == 6  # 3 oldest timestamps x (json+txt)


def test_prune_reports_noop_when_under_keep(tmp_path):
    _mk(tmp_path, "20260101_090000")
    assert report_io.prune_reports(str(tmp_path), keep=30) == []


def test_prune_reports_missing_dir_is_safe():
    assert report_io.prune_reports("/no/such/dir", keep=5) == []
