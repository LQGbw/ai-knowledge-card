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

CREATE TABLE IF NOT EXISTS subscriptions (
    user_id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    subscribed_at TEXT NOT NULL,
    last_pushed_at TEXT,
    push_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS viewed_cards (
    user_id TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    viewed_at TEXT NOT NULL,
    PRIMARY KEY(user_id, card_id)
);

CREATE TABLE IF NOT EXISTS user_stats (
    user_id TEXT PRIMARY KEY,
    menu_view_count INTEGER NOT NULL DEFAULT 0,
    last_menu_at TEXT
);
"""


class BotStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate_subscriptions(connection)

    def _migrate_subscriptions(self, connection: sqlite3.Connection) -> None:
        """将旧版 subscriptions 表（chat_id 为主键）迁移到新版（user_id 为主键）。"""
        try:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(subscriptions)")
            }
        except sqlite3.OperationalError:
            return  # 表不存在，SCHEMA 已创建新版
        if "user_id" not in columns:
            # 旧表结构，备份后重建
            connection.execute("ALTER TABLE subscriptions RENAME TO subscriptions_old")
            connection.execute(
                """
                CREATE TABLE subscriptions (
                    user_id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    subscribed_at TEXT NOT NULL,
                    last_pushed_at TEXT,
                    push_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            print("[迁移] subscriptions 表已升级为按 user_id 订阅，旧数据已备份到 subscriptions_old")

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

    def subscribe(self, user_id: str, chat_id: str) -> bool:
        """订阅（按 user_id，同时记录推送用的 chat_id）。"""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO subscriptions(user_id, chat_id, subscribed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id
                """,
                (user_id, chat_id, _now()),
            )
        return cursor.rowcount > 0

    def unsubscribe(self, user_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM subscriptions WHERE user_id=?",
                (user_id,),
            )
        return cursor.rowcount > 0

    def is_subscribed(self, user_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM subscriptions WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return row is not None

    def update_chat_id(self, user_id: str, chat_id: str) -> None:
        """更新用户的活跃对话（用户在新对话中交互时调用，确保推送到最新对话）。"""
        with self._connect() as connection:
            connection.execute(
                "UPDATE subscriptions SET chat_id=? WHERE user_id=?",
                (chat_id, user_id),
            )

    def all_subscriptions(self) -> list[tuple[str, str]]:
        """返回所有订阅用户：[(user_id, chat_id), ...]。"""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT user_id, chat_id FROM subscriptions ORDER BY subscribed_at"
            ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def record_push(self, user_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE subscriptions
                SET last_pushed_at=?, push_count=push_count+1
                WHERE user_id=?
                """,
                (_now(), user_id),
            )

    def subscription_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM subscriptions"
            ).fetchone()
        return int(row[0]) if row else 0

    # ---- 观看历史 ----

    def record_view(self, user_id: str, card_id: int) -> None:
        """记录用户看过某张卡（重复查看更新时间）。"""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO viewed_cards(user_id, card_id, viewed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, card_id) DO UPDATE SET
                    viewed_at=excluded.viewed_at
                """,
                (user_id, card_id, _now()),
            )

    def viewed_card_ids(self, user_id: str) -> set[int]:
        """返回用户看过的所有卡片ID集合。"""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT card_id FROM viewed_cards WHERE user_id=?",
                (user_id,),
            ).fetchall()
        return {int(row[0]) for row in rows}

    # ---- 使用统计（用于订阅提示）----

    def increment_menu_view(self, user_id: str) -> int:
        """用户查看卡组次数 +1，返回当前次数。"""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_stats(user_id, menu_view_count, last_menu_at)
                VALUES (?, 1, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    menu_view_count=menu_view_count+1,
                    last_menu_at=excluded.last_menu_at
                """,
                (user_id, _now()),
            )
            row = connection.execute(
                "SELECT menu_view_count FROM user_stats WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def menu_view_count(self, user_id: str) -> int:
        """返回用户查看卡组的总次数。"""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT menu_view_count FROM user_stats WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
