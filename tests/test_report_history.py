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
