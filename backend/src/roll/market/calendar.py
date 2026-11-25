"""Shanghai exchange sessions from the adapted annual notices and corrections."""
from datetime import date, timedelta


HOLIDAYS_2026 = [
    ('2026-01-01', '2026-01-03'), ('2026-02-15', '2026-02-23'),
    ('2026-04-04', '2026-04-06'), ('2026-05-01', '2026-05-05'),
    ('2026-06-19', '2026-06-21'), ('2026-09-25', '2026-09-27'),
    ('2026-10-01', '2026-10-07'),
]
# Exact annual notice ranges. The exchange also expressly closes on weekends;
# government makeup working weekends never create an exchange session.
SSE_HISTORICAL_HOLIDAYS = {
    2013: [('01-01', '01-03'), ('02-09', '02-15'), ('04-04', '04-06'),
           ('04-29', '05-01'), ('06-10', '06-12'), ('09-19', '09-21'), ('10-01', '10-07')],
    2014: [('01-01', '01-01'), ('01-31', '02-06'), ('04-07', '04-07'),
           ('05-01', '05-03'), ('06-02', '06-02'), ('09-08', '09-08'), ('10-01', '10-07')],
    2015: [('01-01', '01-03'), ('02-18', '02-24'), ('04-05', '04-06'),
           ('05-01', '05-03'), ('06-20', '06-22'), ('09-27', '09-27'), ('10-01', '10-07')],
    2016: [('01-01', '01-03'), ('02-07', '02-13'), ('04-02', '04-04'),
           ('04-30', '05-02'), ('06-09', '06-11'), ('09-15', '09-17'), ('10-01', '10-07')],
    2017: [('01-01', '01-02'), ('01-27', '02-02'), ('04-02', '04-04'),
           ('04-29', '05-01'), ('05-28', '05-30'), ('10-01', '10-08')],
    2018: [('01-01', '01-01'), ('02-15', '02-21'), ('04-05', '04-07'),
           ('04-29', '05-01'), ('06-16', '06-18'), ('09-22', '09-24'), ('10-01', '10-07')],
    2019: [('01-01', '01-01'), ('02-04', '02-10'), ('04-05', '04-07'),
           ('05-01', '05-01'), ('06-07', '06-09'), ('09-13', '09-15'), ('10-01', '10-07')],
    2020: [('01-01', '01-01'), ('01-24', '01-30'), ('04-04', '04-06'),
           ('05-01', '05-05'), ('06-25', '06-27'), ('10-01', '10-08')],
    2021: [('01-01', '01-03'), ('02-11', '02-17'), ('04-03', '04-05'),
           ('05-01', '05-05'), ('06-12', '06-14'), ('09-19', '09-21'), ('10-01', '10-07')],
    2022: [('01-01', '01-03'), ('01-31', '02-06'), ('04-03', '04-05'),
           ('04-30', '05-04'), ('06-03', '06-05'), ('09-10', '09-12'), ('10-01', '10-07')],
    2023: [('01-01', '01-02'), ('01-21', '01-27'), ('04-05', '04-05'),
           ('04-29', '05-03'), ('06-22', '06-24'), ('09-29', '10-06')],
    2024: [('01-01', '01-01'), ('02-09', '02-17'), ('04-04', '04-06'),
           ('05-01', '05-05'), ('06-10', '06-10'), ('09-15', '09-17'), ('10-01', '10-07')],
    2025: [('01-01', '01-01'), ('01-28', '02-04'), ('04-04', '04-06'),
           ('05-01', '05-05'), ('05-31', '06-02'), ('10-01', '10-08')],
}
# Keep the original annual ranges and later changes separately, with both
# originals exposed. This is current historical reconstruction, not PIT data.
SSE_CALENDAR_CORRECTIONS = {
    2015: [('09-03', '09-05', 'sse-calendar-2015-memorial')],
    # 2019's annual notice explicitly starts its New Year closure in 2018.
    2018: [('12-30', '12-31', 'sse-calendar-2019')],
    2019: [('05-01', '05-04', 'sse-calendar-2019-labor-revision')],
    2020: [('01-31', '02-02', 'sse-calendar-2020-spring-extension')],
}


LAST_NOTICE_DAY = date(2026, 12, 31)


def extended_sessions(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='market_inputs'").fetchone():
        return frozenset()
    return frozenset(r[0] for r in db.execute(
        "SELECT trade_date FROM market_inputs WHERE series='calendar' AND symbol='CN' AND trade_date>?",
        (LAST_NOTICE_DAY.isoformat(),)))


def latest_session(db, cutoff_day):
    extension = extended_sessions(db)
    known_through = max(LAST_NOTICE_DAY, date.fromisoformat(max(extension)) if extension else LAST_NOTICE_DAY)
    cursor = min(known_through, cutoff_day)
    if cursor.year < min(SSE_HISTORICAL_HOLIDAYS):
        raise ValueError('没有此日期之前的已核实交易日')
    while not is_session(cursor, extension):
        cursor -= timedelta(days=1)
    return cursor, cutoff_day > known_through


def is_session(day: date, extension=None) -> bool:
    year = day.year
    if year == 2026:
        ranges = HOLIDAYS_2026
    elif year in SSE_HISTORICAL_HOLIDAYS:
        periods = SSE_HISTORICAL_HOLIDAYS[year] + [
            (start, end) for start, end, _ in SSE_CALENDAR_CORRECTIONS.get(year, [])
        ]
        ranges = [(f"{year}-{start}", f"{year}-{end}") for start, end in periods]
    else:
        if extension is not None:
            return day.isoformat() in extension
        raise ValueError(f"缺少 {year} 年交易日历")
    return day.weekday() < 5 and not any(start <= day.isoformat() <= end for start, end in ranges)
