"""SQLite connection helper and daily backups. The course creates its own sc_* tables."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "song.sqlite3")
LIVE_DB_PATH = DB_PATH


def is_live():
    """True for the learner's real database. Tests and tools redirect DB_PATH, so anything that
    costs money or writes beside the database (model checks, backups) keys off this."""
    return DB_PATH == LIVE_DB_PATH


def get_conn():
    # timeout: wait for locks instead of failing fast. WAL: readers don't block behind a writer.
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def backup_daily(keep=7):
    """One consistent copy of the learning database per day; keeps the newest `keep`.

    sqlite's backup API is safe while the app is writing (it accounts for the WAL), which a plain
    file copy is not."""
    import glob
    from datetime import date
    folder = os.path.join(os.path.dirname(DB_PATH), "data", "backups")
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, f"song-{date.today().isoformat()}.sqlite3")
    if not os.path.exists(target):
        src, dst = sqlite3.connect(DB_PATH), sqlite3.connect(target + ".tmp")
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()
        os.replace(target + ".tmp", target)
    for old in sorted(glob.glob(os.path.join(folder, "song-*.sqlite3")))[:-keep]:
        os.remove(old)
    return target
