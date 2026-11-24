from concurrent.futures import ThreadPoolExecutor
import json

from roll.cli import main
from roll.reports import freeze_report, read_report


def test_concurrent_freezes_and_both_export_formats(tmp_path, capsys):
    day = "2025-08-01"
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(lambda _: freeze_report(tmp_path, day), range(4)))
    report = reports[0]
    assert reports == [report] * 4
    assert report["trade_date"] == day
    assert report["barometer"]["coverage"] == 0
    assert report["barometer"]["score"] is None
    assert report["barometer"]["position_cap"] is None
    assert set(report["missing"]) >= {"600362.SH", "000300.SH"}
    assert read_report(tmp_path, day) == report
    main(["--data-dir", str(tmp_path), "report", "read", day])
    assert json.loads(capsys.readouterr().out) == report
    main(["--data-dir", str(tmp_path), "report", "read", day, "--format", "markdown"])
    markdown = capsys.readouterr().out
    for value in [day, report["cutoff_at"], "600362.SH", "000300.SH", "今日晴雨表不可用", "0%"]:
        assert value in markdown
