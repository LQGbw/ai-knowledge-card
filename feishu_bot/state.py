from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS favorites (
    user_id TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    saved_at TEXT NOT NULL,
    PRIMARY KEY(user_id, card_id)
);

CREATE TABLE IF NOT EXISTS last_reveals (
    user_id TEXT PRIMARY KEY,
    card_id INTEGER NOT NULL,
    revealed_at TEXT NOT NULL
);
"""


class BotStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def remember_reveal(self, user_id: str, card_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO last_reveals(user_id, card_id, revealed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    card_id=excluded.card_id,
                    revealed_at=excluded.revealed_at
                """,
                (user_id, card_id, _now()),
            )

    def last_reveal(self, user_id: str) -> int | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT card_id FROM last_reveals WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return int(row[0]) if row else None

    def add_favorite(self, user_id: str, card_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO favorites(user_id, card_id, saved_at)
                VALUES (?, ?, ?)
                """,
                (user_id, card_id, _now()),
            )
        return cursor.rowcount > 0

    def remove_favorite(self, user_id: str, card_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM favorites WHERE user_id=? AND card_id=?",
                (user_id, card_id),
            )
        return cursor.rowcount > 0

    def is_favorite(self, user_id: str, card_id: int) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM favorites WHERE user_id=? AND card_id=?",
                (user_id, card_id),
            ).fetchone()
        return row is not None

    def favorite_ids(self, user_id: str) -> list[int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT card_id FROM favorites
                WHERE user_id=? ORDER BY saved_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [int(row[0]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
