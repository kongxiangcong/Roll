"""Build SSE trading calendar 2015-10-01..2023-12-31 from archived official notices.

Deterministic rule taken from the notices themselves: a natural day is a trading
day iff it is a weekday AND not listed in the official closure ranges. Weekend
make-up days are never trading days for SSE (verbatim in every notice).
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("D:/dsh-proj/Roll")
NOTICE = ROOT / ".scratch/roll-p0/evidence/19/calendar/official-notice-extract.json"

# Manual, verbatim-grounded closure ranges per archived official notice.
# Each entry: (year_label, published_date, source_id, [ (start, end, label) ])
# Values transcribed from official-notice-extract.json paragraphs.
RANGES = {
    "2015": [  # 2014-12-24 notice + 2015 memorial
        ("2015-01-01", "2015-01-03", "元旦"),
        ("2015-02-18", "2015-02-24", "春节"),
        ("2015-04-06", "2015-04-06", "清明节"),
        ("2015-05-01", "2015-05-01", "劳动节"),
        ("2015-06-22", "2015-06-22", "端午节"),
        ("2015-09-03", "2015-09-04", "抗战胜利70周年纪念日"),
        ("2015-09-27", "2015-09-27", "中秋节"),
        ("2015-10-01", "2015-10-07", "国庆节"),
    ],
    "2016": [
        ("2016-01-01", "2016-01-01", "元旦"),
        ("2016-02-07", "2016-02-13", "春节"),
        ("2016-04-04", "2016-04-04", "清明节"),
        ("2016-05-01", "2016-05-02", "劳动节"),
        ("2016-06-09", "2016-06-11", "端午节"),
        ("2016-09-15", "2016-09-17", "中秋节"),
        ("2016-10-01", "2016-10-07", "国庆节"),
    ],
    "2017": [
        ("2017-01-01", "2017-01-02", "元旦"),
        ("2017-01-27", "2017-02-02", "春节"),
        ("2017-04-02", "2017-04-04", "清明节"),
        ("2017-05-01", "2017-05-01", "劳动节"),
        ("2017-05-28", "2017-05-30", "端午节"),
        ("2017-10-01", "2017-10-08", "国庆节、中秋节"),
    ],
    "2018": [
        ("2018-01-01", "2018-01-01", "元旦"),
        ("2018-02-15", "2018-02-21", "春节"),
        ("2018-04-05", "2018-04-07", "清明节"),
        ("2018-04-29", "2018-05-01", "劳动节"),
        ("2018-06-16", "2018-06-18", "端午节"),
        ("2018-09-22", "2018-09-24", "中秋节"),
        ("2018-10-01", "2018-10-07", "国庆节"),
    ],
    "2019": [
        ("2019-01-01", "2019-01-01", "元旦"),
        ("2019-02-04", "2019-02-10", "春节"),
        ("2019-04-05", "2019-04-07", "清明节"),
        ("2019-05-01", "2019-05-04", "劳动节"),
        ("2019-06-07", "2019-06-09", "端午节"),
        ("2019-09-13", "2019-09-15", "中秋节"),
        ("2019-10-01", "2019-10-07", "国庆节"),
    ],
    "2020": [
        ("2020-01-01", "2020-01-01", "元旦"),
        ("2020-01-24", "2020-02-02", "春节(延长)"),
        ("2020-04-04", "2020-04-06", "清明节"),
        ("2020-05-01", "2020-05-05", "劳动节"),
        ("2020-06-25", "2020-06-27", "端午节"),
        ("2020-10-01", "2020-10-08", "国庆节、中秋节"),
    ],
    "2021": [
        ("2021-01-01", "2021-01-03", "元旦"),
        ("2021-02-11", "2021-02-17", "春节"),
        ("2021-04-03", "2021-04-05", "清明节"),
        ("2021-05-01", "2021-05-05", "劳动节"),
        ("2021-06-12", "2021-06-14", "端午节"),
        ("2021-09-19", "2021-09-21", "中秋节"),
        ("2021-10-01", "2021-10-07", "国庆节"),
    ],
    "2022": [
        ("2022-01-01", "2022-01-03", "元旦"),
        ("2022-01-31", "2022-02-06", "春节"),
        ("2022-04-03", "2022-04-05", "清明节"),
        ("2022-04-30", "2022-05-04", "劳动节"),
        ("2022-06-03", "2022-06-05", "端午节"),
        ("2022-09-10", "2022-09-12", "中秋节"),
        ("2022-10-01", "2022-10-07", "国庆节"),
    ],
    "2023": [
        ("2023-01-01", "2023-01-02", "元旦"),
        ("2023-01-21", "2023-01-27", "春节"),
        ("2023-04-05", "2023-04-05", "清明节"),
        ("2023-04-29", "2023-05-03", "劳动节"),
        ("2023-06-22", "2023-06-24", "端午节"),
        ("2023-09-29", "2023-10-06", "国庆节、中秋节"),
    ],
}


def d(s: str) -> date:
    return date.fromisoformat(s)


def main() -> None:
    for y, ranges in RANGES.items():
        for s, e, _ in ranges:
            assert d(s).year in (int(y), int(y)), (y, s)
    out = []
    cur = d("2015-09-25")
    end = d("2023-12-31")
    holiday_by_date: dict[date, str] = {}
    for y, ranges in RANGES.items():
        for s, e, label in ranges:
            day = d(s)
            while day <= d(e):
                holiday_by_date[day] = label
                day += timedelta(days=1)
    while cur <= end:
        if cur.weekday() >= 5:
            out.append((cur, False, "WEEKEND_CLOSURE"))
        elif cur in holiday_by_date:
            out.append((cur, False, holiday_by_date[cur]))
        else:
            out.append((cur, True, None))
        cur += timedelta(days=1)
    trading = [x for x in out if x[1]]
    # longest run
    best = best_cur = 0
    prev = None
    for day, istrading, _ in out:
        if istrading:
            if prev is not None and (day - prev).days == 1:
                best_cur += 1
            else:
                best_cur = 1
            best = max(best, best_cur)
            prev = day
        else:
            prev = None
    print("trading days:", len(trading), "range", trading[0][0], trading[-1][0])
    print("longest consecutive run:", best)
    (HERE / "calendar-built.json").write_text(
        json.dumps({"days": [[x[0].isoformat(), x[1], x[2]] for x in out], "longest_run": best},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    # sanity: 2015-12-31 must be trading (context needs 21 rows before 2016-01-01)
    print("2015-12-31 trading:", [x for x in out if x[0].isoformat() == "2015-12-31"])


if __name__ == "__main__":
    main()
