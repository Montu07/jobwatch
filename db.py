# db.py
import sqlite3
from pathlib import Path

# Keep jobs.db inside ./state so GitHub Actions can persist it as an artifact
STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
DB = STATE_DIR / "jobs.db"


def get_conn():
    conn = sqlite3.connect(DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            remote INTEGER,
            url TEXT,
            posted_at TEXT,
            description TEXT,
            source TEXT
        )
        """
    )
    return conn


def insert_if_new(conn, job):
    """
    Insert a job if not already present.
    Returns True if inserted (new job), False if duplicate.
    """
    try:
        conn.execute(
            """
            INSERT INTO jobs (id, title, company, location, remote, url, posted_at, description, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.get("id"),
                job.get("title"),
                job.get("company"),
                job.get("location"),
                int(job.get("remote", False)),
                job.get("url"),
                job.get("posted_at"),
                job.get("description"),
                job.get("source"),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
