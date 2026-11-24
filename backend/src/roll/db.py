"""SQLite connection settings shared by all modules in the local workbench."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        yield db
    finally:
        db.close()
