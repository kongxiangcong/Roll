"""SQLite connection settings shared by all modules in the local workbench."""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        db.row_factory = sqlite3.Row
        # Concurrent first opens can return SQLITE_BUSY before busy_timeout
        # applies to the journal-mode change.
        deadline = time.monotonic() + 10
        while True:
            try:
                db.execute("PRAGMA journal_mode=WAL").fetchone()
                break
            except sqlite3.OperationalError as error:
                if error.sqlite_errorcode != sqlite3.SQLITE_BUSY or time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        yield db
    finally:
        db.close()
