"""db.backup_daily: one readable copy per day, oldest pruned. Run: python -X utf8 test_backup.py"""
import os
import sqlite3
import tempfile

import db


def demo():
    with tempfile.TemporaryDirectory() as folder:
        db.DB_PATH = os.path.join(folder, "song.sqlite3")
        conn = sqlite3.connect(db.DB_PATH)
        conn.execute("CREATE TABLE t(x)")
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()
        conn.close()
        backups = os.path.join(folder, "data", "backups")
        os.makedirs(backups)
        for day in range(1, 10):   # nine older copies already on disk
            open(os.path.join(backups, f"song-2026-01-0{day}.sqlite3"), "w").close()

        target = db.backup_daily(keep=7)
        copy = sqlite3.connect(target)
        assert copy.execute("SELECT x FROM t").fetchone() == (42,)
        copy.close()
        kept = sorted(os.listdir(backups))
        assert len(kept) == 7 and os.path.basename(target) in kept, kept
        assert db.backup_daily(keep=7) == target   # second call the same day is a no-op
    print("backup ok")


if __name__ == "__main__":
    demo()
