"""SQLite connections and timestamps shared by the v3 application."""
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from roll.market.calendar import is_session


SHANGHAI = ZoneInfo("Asia/Shanghai")


def instant(value=None):
    if value is None:
        return datetime.now(SHANGHAI)
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed.astimezone(SHANGHAI) if parsed.tzinfo else parsed.replace(tzinfo=SHANGHAI)


def timestamp(value=None):
    return instant(value).isoformat(timespec="microseconds")


def session_time(day, hour, minute=0):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    return datetime.combine(day, time(hour, minute), SHANGHAI)


def sessions(start, end):
    day, last = date.fromisoformat(start), date.fromisoformat(end)
    while day <= last:
        if is_session(day):
            yield day.isoformat()
        day += timedelta(days=1)


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


@contextmanager
def database(data_dir, *, write=False, db=None):
    if db is not None:
        if write and not db.in_transaction:
            with db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        else:
            yield db
        return
    directory = Path(data_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(directory / "roll-v3.sqlite3", timeout=15)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 15000")
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA synchronous = NORMAL")
        with db:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db


def ensure_schema(db, schema):
    """Initialize known static DDL without implicitly committing an outer transaction."""
    for statement in schema.split(";"):
        if statement.strip():
            db.execute(statement)
