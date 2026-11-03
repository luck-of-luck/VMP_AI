"""Deterministic playground seed for SQLite: answers in docs/evals/evaluation-sqlite.json depend on this data.

Usage: python scripts/seed/sqlite.py <path-to-db-file>  (make seed writes temp/playground.db)
"""

import sqlite3
import sys


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip())
    conn = sqlite3.connect(sys.argv[1])
    conn.executescript(
        """
        DROP TABLE IF EXISTS tasks;
        DROP TABLE IF EXISTS notes;
        CREATE TABLE tasks (
            id integer PRIMARY KEY,
            title text NOT NULL,
            done integer NOT NULL DEFAULT 0
        );
        CREATE VIRTUAL TABLE notes USING fts5(title, body);
        """
    )
    conn.executemany(
        "INSERT INTO tasks (id, title, done) VALUES (?, ?, ?)",
        [(i, f"task_{i}", 1 if i <= 8 else 0) for i in range(1, 26)],
    )
    conn.executemany(
        "INSERT INTO notes VALUES (?, ?)",
        [
            ("alpha", "postgres full text search"),
            ("beta", "sqlite fts5 index"),
            ("gamma", "redis in memory store"),
        ],
    )
    conn.execute("ANALYZE")
    conn.commit()
    conn.close()
    print(f"seeded {sys.argv[1]}: tasks=25 (8 done), notes=3 (fts5)")


if __name__ == "__main__":
    main()
