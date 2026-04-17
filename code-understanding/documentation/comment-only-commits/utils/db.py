import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    repo     TEXT NOT NULL UNIQUE,
    clone_url TEXT NOT NULL,
    stars    INTEGER,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS commits (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id        INTEGER NOT NULL,
    commit_hash    TEXT NOT NULL,
    commit_date    TEXT NOT NULL,
    commit_message TEXT,
    author_id      TEXT,
    UNIQUE (repo_id, commit_hash),
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

CREATE TABLE IF NOT EXISTS comments (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_id                   INTEGER NOT NULL,
    file_path                   TEXT,
    added_comment               TEXT,
    comment_type                TEXT,
    target_method               TEXT,
    target_class                TEXT,
    code_intro_commit           TEXT,
    code_intro_date             TEXT,
    time_gap_days               REAL,
    original_author_id          TEXT,
    is_different_author         INTEGER,
    cyclomatic_complexity       REAL,
    cognitive_complexity        REAL,
    loc                         INTEGER,
    parameter_count             INTEGER,
    avg_identifier_length       REAL,
    abbrev_ratio                REAL,
    message_has_clarify_keyword INTEGER,
    FOREIGN KEY (commit_id) REFERENCES commits(id)
);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)


def insert_repo(conn: sqlite3.Connection, repo: str, clone_url: str, stars: int, last_updated: str) -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO repos (repo, clone_url, stars, last_updated) VALUES (?, ?, ?, ?)",
        (repo, clone_url, stars, last_updated),
    )
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute("SELECT id FROM repos WHERE repo = ?", (repo,)).fetchone()
    return row["id"]


def insert_commit(conn: sqlite3.Connection, repo_id: int, commit_hash: str, commit_date: str,
                  commit_message: str, author_id: str) -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO commits (repo_id, commit_hash, commit_date, commit_message, author_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (repo_id, commit_hash, commit_date, commit_message, author_id),
    )
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute(
        "SELECT id FROM commits WHERE repo_id = ? AND commit_hash = ?", (repo_id, commit_hash)
    ).fetchone()
    return row["id"]


def insert_comment(conn: sqlite3.Connection, **kwargs) -> None:
    keys = ", ".join(kwargs.keys())
    placeholders = ", ".join("?" * len(kwargs))
    conn.execute(f"INSERT INTO comments ({keys}) VALUES ({placeholders})", list(kwargs.values()))
