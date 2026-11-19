"""SQLite 存储：消息去重、按天归档、文档记录。"""
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL UNIQUE,
    title        TEXT NOT NULL,
    summary      TEXT NOT NULL DEFAULT '',
    source_id    TEXT NOT NULL DEFAULT '',
    source_name  TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    day          TEXT NOT NULL,
    first_seen   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_news_day ON news(day);
CREATE INDEX IF NOT EXISTS idx_news_pub ON news(published_at);

CREATE TABLE IF NOT EXISTS digests (
    day        TEXT PRIMARY KEY,
    filename   TEXT NOT NULL,
    item_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # ---------- 消息 ----------
    def add_items(self, items):
        """插入消息，返回真正新增的那部分。"""
        added = []
        with self.lock:
            for item in items:
                cur = self.conn.execute(
                    """INSERT OR IGNORE INTO news
                       (url, title, summary, source_id, source_name, published_at, day, first_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item["url"],
                        item["title"],
                        item.get("summary", ""),
                        item.get("source_id", ""),
                        item.get("source_name", ""),
                        item.get("published_at", ""),
                        item["day"],
                        item["first_seen"],
                    ),
                )
                if cur.rowcount:
                    added.append(item)
            self.conn.commit()
        return added

    def existing_urls(self, urls):
        urls = [u for u in urls if u]
        if not urls:
            return set()
        found = set()
        with self.lock:
            for i in range(0, len(urls), 500):
                chunk = urls[i:i + 500]
                marks = ",".join("?" * len(chunk))
                rows = self.conn.execute(
                    f"SELECT url FROM news WHERE url IN ({marks})", chunk
                ).fetchall()
                found.update(r["url"] for r in rows)
        return found

    def list_by_day(self, day, limit=200):
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM news WHERE day = ?
                   ORDER BY published_at DESC, id DESC LIMIT ?""",
                (day, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_recent(self, limit=200):
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM news
                   ORDER BY day DESC, published_at DESC, id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def day_counts(self, limit=90):
        with self.lock:
            rows = self.conn.execute(
                """SELECT day, COUNT(*) AS count FROM news
                   GROUP BY day ORDER BY day DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def total(self):
        with self.lock:
            row = self.conn.execute("SELECT COUNT(*) AS c FROM news").fetchone()
        return int(row["c"])

    # ---------- 文档 ----------
    def upsert_digest(self, day, filename, item_count, created_at):
        with self.lock:
            self.conn.execute(
                """INSERT INTO digests (day, filename, item_count, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(day) DO UPDATE SET
                     filename = excluded.filename,
                     item_count = excluded.item_count,
                     created_at = excluded.created_at""",
                (day, filename, item_count, created_at),
            )
            self.conn.commit()

    def get_digest(self, day):
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM digests WHERE day = ?", (day,)
            ).fetchone()
        return dict(row) if row else None

    def list_digests(self, limit=60):
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM digests
                   ORDER BY day DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- 杂项 ----------
    def meta_get(self, key, default=None):
        with self.lock:
            row = self.conn.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def meta_set(self, key, value):
        with self.lock:
            self.conn.execute(
                """INSERT INTO meta (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, value),
            )
            self.conn.commit()
