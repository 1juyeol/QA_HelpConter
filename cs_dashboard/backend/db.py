import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "cs_dashboard.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY,
                created_date TEXT NOT NULL,
                complete_date TEXT,
                category_tag INTEGER,
                category_main TEXT,
                category_sub TEXT,
                category_full TEXT,
                call_memo TEXT
            )
        """)
        try:
            conn.execute("ALTER TABLE issues ADD COLUMN call_memo TEXT")
        except Exception:
            pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created_date ON issues(created_date)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_at TEXT DEFAULT (datetime('now', 'localtime')),
                date_target TEXT,
                count_fetched INTEGER,
                status TEXT,
                message TEXT
            )
        """)
        conn.commit()
